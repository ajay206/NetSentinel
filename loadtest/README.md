# Load test (W23)

`make k3d-load` runs `locustfile.py` headless against `http://localhost:8080` (k3d ingress):
20 users (3 viewers per operator), spawn rate 2/s, 3 minutes. It samples the copilot replica
count every 10 s and writes `report.md`. `report.md` is generated, so commit it only from a
real run on the Mac.
