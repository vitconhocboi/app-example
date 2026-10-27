# taxi-fare-app

App Dash mau (port tu vi du Databricks Apps "Taxi Fare Distribution") chay sau SSO forward-auth,
truy van SQL qua `datanexus` voi `X-Forwarded-Access-Token` (query chay duoi quyen user dang nhap).

- Scatter `trip_distance` x `fare_amount`, bang AG Grid (5000 dong dau).
- "Predict Fare": `AVG(fare_amount)` theo cap zipcode, tinh tren server voi tham so `:pickup`, `:dropoff`.

Env:

| Bien | Mac dinh | |
|---|---|---|
| `DATANEXUS_HOST` | — | vd `http://host.docker.internal:8000` |
| `DATANEXUS_CONNECTION_ID` | — | connection user co quyen |
| `DATANEXUS_TAXI_TABLE` | `samples.nyctaxi.trips` | can cot `trip_distance, fare_amount, pickup_zip, dropoff_zip` |
| `DATANEXUS_ROW_LIMIT` | `5000` | |

Build:

```bash
docker build --build-context datanexus=../appvisualize/lib/datanexus -t taxi-fare-app .
```

Chay e2e sau nginx forward-auth: dung `appvisualize/deploy/sso-demo`, thay service
`sso-demo-app` bang image nay (cung port 8501).

Chay local (khong co SSO thi app bao thieu token):

```bash
pip install -r requirements.txt "../appvisualize/lib/datanexus[arrow]"
DATANEXUS_HOST=... DATANEXUS_CONNECTION_ID=... python app.py   # http://localhost:8501
```
