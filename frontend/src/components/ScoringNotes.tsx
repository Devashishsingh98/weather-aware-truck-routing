export function ScoringNotes() {
  return (
    <details className="scoring-notes">
      <summary>How a route gets picked</summary>
      <p>
        Each checkpoint takes the worst of wind, rain, and snow. Miles between two checkpoints are
        charged to the worse of those two samples. No Travel miles are disqualifying: they sort
        ahead of Severe miles, so a short blocked corridor loses to a longer clean one.
      </p>
      <table>
        <thead>
          <tr>
            <th>Condition</th>
            <th>Low</th>
            <th>Moderate</th>
            <th>High</th>
            <th>Severe</th>
            <th>No Travel</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th>Wind</th>
            <td>&lt;25 mph</td>
            <td>25–34</td>
            <td>35–44</td>
            <td>45–54</td>
            <td>≥55</td>
          </tr>
          <tr>
            <th>Rain</th>
            <td>&lt;0.10 in/hr</td>
            <td>0.10–0.25</td>
            <td>0.25–0.50</td>
            <td>0.50–1.00</td>
            <td>&gt;1.00</td>
          </tr>
          <tr>
            <th>Snow</th>
            <td>&lt;0.5 in/hr</td>
            <td>0.5–1.0</td>
            <td>1.0–2.0</td>
            <td>2.0–3.0</td>
            <td>&gt;3.0</td>
          </tr>
        </tbody>
      </table>
      <ul>
        <li>Shared rain and snow endpoints take the worse band. 1.00 in/hr of rain and 3.0 in/hr of snow stay Severe.</li>
        <li>34.9 mph is still Moderate. 35.0 mph is High. The same cuts apply at 45 and 55.</li>
        <li>≥55 mph is No Travel for any load.</li>
        <li>45–54 mph and a load over 30,000 lb is No Travel.</li>
        <li>35–44 mph and a load over 40,000 lb is raised to Severe.</li>
        <li>Then: fewest Severe miles, fewest High miles, lowest mileage-weighted risk, shortest drive.</li>
      </ul>
    </details>
  )
}
