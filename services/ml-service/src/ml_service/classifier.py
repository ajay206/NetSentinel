"""Fault-type classifier inference wrapper.

Loads a trained XGBoost booster and provides predict / explain APIs.
SHAP values are computed via XGBoost's built-in TreeSHAP
(booster.predict with pred_contribs=True). No shap package.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xgboost as xgb

from .features import FEATURE_NAMES, alarm_features
from .synth_faults import FAULT_TYPES


class FaultClassifier:
    """Wrapper around a trained XGBoost fault classifier."""

    def __init__(self, booster: xgb.Booster, meta: dict, model_version: str) -> None:
        self._booster = booster
        self._meta = meta
        self._model_version = model_version
        self._feature_names: list[str] = meta.get("feature_names", list(FEATURE_NAMES))
        self._fault_types: list[str] = meta.get("fault_types", list(FAULT_TYPES))

    @classmethod
    def load(
        cls,
        name: str = "fault_classifier",
        models_dir: str = "models",
        version: str = "latest",
    ) -> FaultClassifier:
        """Load a classifier from disk.

        Args:
            name: model name (sub-directory under models_dir).
            models_dir: base models directory.
            version: version string or "latest".

        Returns:
            FaultClassifier instance.

        Raises:
            FileNotFoundError: if the registry or model files are missing.
        """
        base = Path(models_dir)
        registry_path = base / "registry.json"
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry not found: {registry_path}")

        registry = json.loads(registry_path.read_text())
        entry = registry.get(name)
        if entry is None:
            raise FileNotFoundError(f"No entry for '{name}' in registry")

        if version == "latest":
            version = entry.get("latest")
            if version is None:
                raise FileNotFoundError(f"No latest version for '{name}'")

        version_dir = base / name / version
        if not version_dir.exists():
            raise FileNotFoundError(f"Version directory not found: {version_dir}")

        model_path = version_dir / "model.json"
        meta_path = version_dir / "meta.json"
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        if not meta_path.exists():
            raise FileNotFoundError(f"Meta file not found: {meta_path}")

        booster = xgb.Booster()
        booster.load_model(str(model_path))
        meta = json.loads(meta_path.read_text())

        return cls(booster, meta, version)

    def _to_dmatrix(self, alarm: dict, context: dict | None = None) -> xgb.DMatrix:
        vec = alarm_features(alarm, context)
        return xgb.DMatrix(
            vec.reshape(1, -1),
            feature_names=list(self._feature_names),
        )

    def predict(self, alarm: dict, context: dict | None = None) -> dict:
        """Predict the fault type for an alarm.

        Returns:
            dict with faultType, confidence, probabilities, modelVersion.
        """
        dmatrix = self._to_dmatrix(alarm, context)
        proba = self._booster.predict(dmatrix)  # (1, n_classes)
        proba = np.asarray(proba).reshape(-1)
        class_idx = int(np.argmax(proba))
        fault_type = self._fault_types[class_idx]
        confidence = float(proba[class_idx])
        probabilities = {
            self._fault_types[i]: round(float(proba[i]), 4) for i in range(len(self._fault_types))
        }
        return {
            "faultType": fault_type,
            "confidence": round(confidence, 4),
            "probabilities": probabilities,
            "modelVersion": self._model_version,
        }

    def explain(self, alarm: dict, context: dict | None = None, top_k: int = 5) -> dict:
        """Explain a prediction using TreeSHAP contributions.

        Returns:
            dict with faultType, confidence, modelVersion, baseValue,
            contributions (top_k by |shap| for the predicted class).
        """
        dmatrix = self._to_dmatrix(alarm, context)
        proba = np.asarray(self._booster.predict(dmatrix)).reshape(-1)
        class_idx = int(np.argmax(proba))
        fault_type = self._fault_types[class_idx]
        confidence = float(proba[class_idx])

        # TreeSHAP contributions.
        contribs = self._booster.predict(dmatrix, pred_contribs=True)
        contribs = np.asarray(contribs)

        # Handle shape variations across xgboost versions.
        # Expected for multi-class: (n_samples, n_classes, n_features+1)
        # Older versions may return: (n_samples, (n_features+1)*n_classes)
        if contribs.ndim == 2 and contribs.shape[0] == 1:
            n_features = len(self._feature_names)
            expected_cols = (n_features + 1) * len(self._fault_types)
            if contribs.shape[1] == expected_cols:
                contribs = contribs.reshape(1, len(self._fault_types), n_features + 1)

        # Extract contributions for the predicted class.
        if contribs.ndim == 3:
            # (1, n_classes, n_features+1)
            class_contribs = contribs[0, class_idx, :]
        else:
            # (1, n_features+1) — single class or already reduced
            class_contribs = contribs[0, :]

        # Last column is the bias (base value).
        base_value = float(class_contribs[-1])
        feature_shaps = class_contribs[:-1]

        # Build contribution list.
        feats = alarm_features(alarm, context)
        contributions = []
        for i, fname in enumerate(self._feature_names):
            contributions.append(
                {
                    "feature": fname,
                    "value": float(feats[i]),
                    "shap": round(float(feature_shaps[i]), 4),
                }
            )

        # Sort by absolute shap value descending and take top_k.
        contributions.sort(key=lambda c: abs(c["shap"]), reverse=True)
        top_contributions = contributions[:top_k]

        return {
            "faultType": fault_type,
            "confidence": round(confidence, 4),
            "modelVersion": self._model_version,
            "baseValue": round(base_value, 4),
            "contributions": top_contributions,
        }
