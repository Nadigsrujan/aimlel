import React, { useEffect, useState } from "react";

const percent = (value) => `${(100 * value).toFixed(1)}%`;
const interval = (value) =>
  value ? `${percent(value.lower)}–${percent(value.upper)}` : "—";

export default function FinalStudy() {
  const [report, setReport] = useState(null);
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const response = await fetch("/assets/study-results.json", {
          cache: "no-cache",
        });
        if (!response.ok) return;
        const value = await response.json();
        if (active && value.status === "frozen held-out evaluation")
          setReport(value);
      } catch {
        /* The artifact is published after the frozen study completes. */
      }
    }
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  if (!report)
    return (
      <div className="final-study research-empty">
        <strong>Held-out scores are not published yet.</strong>
        <p>The frozen study must complete before its results appear here.</p>
      </div>
    );
  const baseline = report.strongest_baseline;
  const names = ["heterogeneous", baseline];
  const projects = Object.keys(report.per_repository.heterogeneous);
  const ablations = [
    ...Object.entries(report.macro).filter(([name]) => name.endsWith("-only")),
    ...Object.entries(report.leave_one_out || {}),
  ];
  return (
    <section className="final-study">
      <div className="section-heading">
        <div>
          <span className="section-tag">FROZEN / UNSEEN PROJECTS</span>
          <h3>The held-out result.</h3>
        </div>
        <span
          className={`study-outcome ${report.success_gate_met ? "met" : "unmet"}`}
        >
          {report.success_gate_met
            ? "Ranking gate met"
            : "Ranking gate not met"}
        </span>
      </div>
      <p className="result-note">
        {report.query_count} commit queries · SymPy, scikit-learn, Django ·
        repository-macro metrics. The gate requires gains in both Recall@5 and
        NDCG@10 over the validation-selected baseline.
      </p>
      <div className="study-table">
        <table>
          <thead>
            <tr>
              <th>Frozen system</th>
              <th>Recall@5</th>
              <th>95% interval</th>
              <th>NDCG@10</th>
              <th>Candidate ceiling</th>
            </tr>
          </thead>
          <tbody>
            {names.map((name) => (
              <tr key={name}>
                <th>
                  {name === "heterogeneous" ? "Fusion GraphSAGE" : baseline}
                </th>
                <td>{percent(report.macro[name].recall_at_5)}</td>
                <td>
                  {interval(report.confidence_intervals[name].recall_at_5)}
                </td>
                <td>{report.macro[name].ndcg_at_10.toFixed(3)}</td>
                <td>{percent(report.macro[name].candidate_ceiling)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h4>Across repositories</h4>
      <div className="study-table">
        <table>
          <thead>
            <tr>
              <th>Project</th>
              <th>Fusion Recall@5</th>
              <th>Baseline Recall@5</th>
              <th>Fusion NDCG@10</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((repo) => (
              <tr key={repo}>
                <th>{repo}</th>
                <td>
                  {percent(
                    report.per_repository.heterogeneous[repo].recall_at_5,
                  )}
                </td>
                <td>
                  {percent(report.per_repository[baseline][repo].recall_at_5)}
                </td>
                <td>
                  {report.per_repository.heterogeneous[repo].ndcg_at_10.toFixed(
                    3,
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!!ablations.length && (
        <>
          <h4>Evidence contribution</h4>
          <p className="result-note">
            Single-channel and channel-removal models use the same held-out
            queries and candidate pools.
          </p>
          <div className="study-table">
            <table>
              <thead>
                <tr>
                  <th>Ablation</th>
                  <th>Recall@5</th>
                  <th>NDCG@10</th>
                </tr>
              </thead>
              <tbody>
                {ablations.map(([name, values]) => (
                  <tr key={name}>
                    <th>{name.replace(/-/g, " ")}</th>
                    <td>{percent(values.recall_at_5)}</td>
                    <td>{values.ndcg_at_10.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {typeof report.channel_removal_gate_met === "boolean" && (
            <p className="result-note">
              {report.channel_removal_gate_met
                ? "Removing each individual channel reduced both measured ranking metrics."
                : "Channel-removal results do not demonstrate a gain from every signal."}
            </p>
          )}
        </>
      )}
      {(report.swebench || report.bugsinpy) && (
        <>
          <h4>Exploratory external cases</h4>
          <p className="result-note">
            A known changed file is the seed. These checks measure file ranking,
            not issue repair or benchmark test-suite reproduction.
          </p>
          <div className="study-table">
            <table>
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Cases</th>
                  <th>Fusion Recall@5</th>
                  <th>Baseline Recall@5</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["SWE-bench Verified", report.swebench],
                  ["BugsInPy", report.bugsinpy],
                ]
                  .filter(([, value]) => value)
                  .map(([name, value]) => (
                    <tr key={name}>
                      <th>{name}</th>
                      <td>{value.cases}</td>
                      <td>
                        {percent(value.metrics.heterogeneous.recall_at_5)}
                      </td>
                      <td>{percent(value.metrics[baseline].recall_at_5)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {report.calibration && (
        <details>
          <summary>Calibration diagnostic · held-out pairs</summary>
          <p>
            Validation-fitted calibrator, assessed on held-out pairs. AP{" "}
            {report.calibration.average_precision.toFixed(4)} · Brier{" "}
            {report.calibration.brier.toFixed(6)} · F1{" "}
            {report.calibration.f1.toFixed(3)} at threshold{" "}
            {report.calibration.threshold}. Heavy class imbalance and sparse
            bins limit interpretation; online scores remain uncalibrated ranking
            values.
          </p>
          <div className="study-table">
            <table>
              <thead>
                <tr>
                  <th>Probability bin</th>
                  <th>Pairs</th>
                  <th>Mean calibrated estimate</th>
                  <th>Observed frequency</th>
                </tr>
              </thead>
              <tbody>
                {report.calibration.reliability_bins.map((b) => (
                  <tr key={b.lower}>
                    <td>
                      {b.lower.toFixed(1)}–{b.upper.toFixed(1)}
                    </td>
                    <td>{b.pairs.toLocaleString()}</td>
                    <td>
                      {b.mean_probability == null
                        ? "Unavailable"
                        : b.mean_probability.toFixed(5)}
                    </td>
                    <td>
                      {b.observed_frequency == null
                        ? "Unavailable"
                        : b.observed_frequency.toFixed(5)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      {report.supplemental_comparators && (
        <details>
          <summary>All frozen comparators · same held-out pool</summary>
          <p>
            {report.supplemental_comparators.status}. The validation-selected
            primary baseline and success gate are unchanged.
          </p>
          <div className="study-table">
            <table>
              <thead>
                <tr>
                  <th>Comparator</th>
                  <th>Recall@5</th>
                  <th>Recall@10</th>
                  <th>MAP@10</th>
                  <th>NDCG@10</th>
                  <th>MRR</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(report.supplemental_comparators.macro).map(
                  ([name, m]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{percent(m.recall_at_5)}</td>
                      <td>{percent(m.recall_at_10)}</td>
                      <td>{m.map_at_10.toFixed(3)}</td>
                      <td>{m.ndcg_at_10.toFixed(3)}</td>
                      <td>{m.mrr.toFixed(3)}</td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        </details>
      )}
      <details>
        <summary>Provenance and limits</summary>
        <p>
          Model <code>{report.model_sha256}</code>
        </p>
        <p>
          Report <code>{report.report_sha256}</code>
        </p>
        <ul>
          {report.limitations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <a href="/assets/study-results.json" download>
          Download study summary ↗
        </a>
      </details>
    </section>
  );
}
