# Business case: Time-Series Analytics

**Store, chart and flag unusual readings from sensors and feeds, with InfluxDB and Grafana.**

## Who buys this

The buyer is an operations or facilities lead at a city department, building manager or small industrial site that collects sensor readings. The users are operators watching dashboards and engineers who get alerted.

## The problem and what it costs

Readings pile up in spreadsheets or vendor portals, and nobody notices a spike until it causes a complaint. A time-series database plus dashboards and simple anomaly detection is the standard fix. The repo's sample schema follows the UCI Beijing multi-site air-quality dataset ([UCI](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data)), and live weather comes from Open-Meteo ([Open-Meteo](https://open-meteo.com)). I found no reliable public figure for the cost of a missed anomaly, so the model below uses assumptions.

## How the repo solves it

| Need | What in the repo does it |
|---|---|
| Store | InfluxDB 2 with Flux queries, for cheap retention and time-window aggregation |
| Chart | Grafana dashboards provisioned as code |
| Flag anomalies | `GET /api/anomalies`: an hourly mean and a rolling 24-hour z-score (the window excludes the point) |
| Live feed | Current weather from Open-Meteo, or weatherapi.com with a key |
| Deploy | Terraform for Cloud Run, Azure Container Apps and AWS ECS |

## Use-case scenarios

All of these organisations are fictional.

1. **A municipal environment office** charts PM2.5 by station and gets a flag when one reading jumps well above its recent average.
2. **A building manager** tracks temperature and humidity per floor and catches a failing air handler early.
3. **A small factory** watches line sensors and reviews the anomaly list each shift.

## ROI: a worked model (illustrative)

These figures are **illustrative assumptions** unless a source is linked.

| Input | Value | Basis |
|---|---|---|
| Equipment incidents a year that earlier detection would shorten | 6 | Assumption |
| Cost per incident-day | US$3,000 | Assumption |
| Days saved per incident | 1 | Assumption |

Avoided cost: 6 × $3,000 = **US$18,000 a year**, against a small InfluxDB and Grafana deployment.

## Path to production

1. Connect real sensors (MQTT, Telegraf or a vendor API).
2. Tune anomaly thresholds per signal, and add alert routing.
3. Set retention and downsampling policies.

## Risks and limits

- A z-score flags unusual values, not faults. Expect false alarms until thresholds are tuned.
- The default air-quality data is synthetic, and the real UCI data is from 2013 to 2017.

**Case strength:** **Moderate.** A real, common need with a standard stack. The anomaly method is deliberately simple.

## Sources

- UCI, Beijing Multi-Site Air Quality dataset: https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data
- Open-Meteo: https://open-meteo.com
