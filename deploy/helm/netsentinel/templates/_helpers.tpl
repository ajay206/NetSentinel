{{- define "ns.labels" -}}
app.kubernetes.io/part-of: netsentinel
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "ns.image" -}}
{{- $root := index . 0 -}}{{- $name := index . 1 -}}
{{- if $root.Values.image.registry -}}
{{ $root.Values.image.registry }}/netsentinel-{{ $name }}:{{ $root.Values.image.tag }}
{{- else -}}
netsentinel-{{ $name }}:{{ $root.Values.image.tag }}
{{- end -}}
{{- end -}}
