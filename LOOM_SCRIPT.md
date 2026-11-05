# Loom walkthrough (about 8 minutes)

Record the running app at http://127.0.0.1:8742 with the Django API on port 8741. Start on the empty map, then use the prefilled Dallas → Denver haul. Speak to the decision, not the file tree.

## 1. What the dispatcher is deciding (0:00–0:45)

- This is a haul planner, not a generic map.
- The driver gives an origin, a destination, a departure clock time, and a load in pounds.
- The app returns three driving options, samples weather at the truck's ETA, and picks a corridor.
- Say that correctness of the risk table matters more than extra features.

## 2. Plan the sample haul (0:45–3:00)

- Point at the prefilled form: Dallas, TX, Denver, CO, tomorrow 08:00, 35,000 lb, every 25 miles.
- Say the departure is read as local time at the origin, so 08:00 means 08:00 in Dallas, not the browser's zone.
- Click **Plan haul**. While it loads, say the API is geocoding, asking OSRM for alternatives, and batching Open-Meteo for every checkpoint.
- When the map appears, name the three lines: Direct, Alternate corridor, and the eastern detour.
- Open the note under the recommendation. OSRM's public router returned two alternatives for this pair, so the third route is a real drive through a waypoint offset perpendicular to the primary corridor.
- Click the Direct card, then the eastern detour, and show the highlight moving.
- Click a checkpoint. Read wind mph, rain in/hr, snow in/hr, the ETA, and which condition set the color.
- Read the rank line: with this forecast the corridors are all Low, so Direct wins because it is about 50 minutes shorter. Say that a Severe or No Travel mile would have beaten that.

## 3. How the score is computed (3:00–5:00)

- Open **How a route gets picked**.
- Walk the table once: wind cuts at 25, 35, 45, and 55; rain at 0.10, 0.25, 0.50, and just over 1.00; snow at 0.5, 1, 2, and just over 3.
- Call out two boundaries: 34.9 mph is still Moderate and 35.0 is High. 1.00 in/hr of rain stays Severe because No Travel is strictly greater than 1.00.
- Load, since this trailer is 35,000 lb: 45–54 mph would be No Travel (over 30,000). 35–44 mph would become Severe only above 40,000 lb, so this load does not trip that rule.
- Miles between checkpoints take the worse of the two samples.
- Order: No Travel miles first (disqualifying, worse than Severe), then Severe, then High, then average risk, then drive time.

## 4. The 48-hour slider (5:00–6:15)

- Scroll to **Next 48 hours**. Drag the slider from 0 to 24 and then toward 48.
- Say the grid was fetched once. Dragging does not call the network. The canvas redraws from the cached hours.
- Point at "Corridor peak at this hour." On this November sample it stays Low. If a later hour were Severe, the field would shift from green toward red and purple without another request.
- Toggle **Show on map** off and on so the routes stay readable.

## 5. Change the sample interval (6:15–7:00)

- Click **Edit**, switch the interval to 10 miles, and plan again.
- Show the checkpoint count jump (about 33 to about 80 on the direct route) and that the ETAs still follow driving time, not a straight-line average.

## 6. Code and deploy (7:00–8:00)

- Show `backend/planner/tests/test_risk.py` and `test_scoring.py`. Say the boundaries and the "No Travel beats any amount of Severe" ordering are unit-tested without the network.
- Mention the stack: Django REST for routing, sampling, weather, and scoring; Vite React and Leaflet for the map.
- Mention free hosting: `render.yaml` plus the backend Dockerfile for the API, Vercel or Netlify for the frontend, `VITE_API_BASE_URL` pointing at the API. CORS already allows `*.vercel.app` and `*.netlify.app`.
- Close on the limits: car routing rather than a truck network, no hours-of-service breaks, and public OSRM sometimes needs the waypoint fallback.
