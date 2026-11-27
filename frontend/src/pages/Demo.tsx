import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAnalysisStore } from "../analysisStore";
import { AnalysisView } from "../components/AnalysisView";
import { DEMO_SCENARIOS } from "../data/demo";

/**
 * The sample results screen: a synthetic candidate and posting with pre-recorded suggestions.
 * No upload and no language model are involved; accepting, previewing and the PDF use the same
 * deterministic API as the real flow.
 */
export function Demo() {
  const [scenarioId, setScenarioId] = useState(DEMO_SCENARIOS[0].id);
  const scenario = DEMO_SCENARIOS.find((s) => s.id === scenarioId) ?? DEMO_SCENARIOS[0];
  const store = useAnalysisStore(scenario.cv);
  const { seed } = store;

  useEffect(() => {
    seed({ posting: scenario.posting, domain: "", careerGoal: "" }, scenario.result);
  }, [scenario, seed]);

  return (
    <section className="step wide">
      <div className="page-title">
        <h1>Demo</h1>
        <span className="badge">Sample data</span>
        <Link to="/" className="link-secondary">Use my own CV</Link>
      </div>
      <p className="notice" role="note">
        The analysis below is <strong>pre-recorded</strong>: no language model is called here. It shows
        what the real flow returns for a synthetic CV and posting, including the proposals the checks removed.
        Accepting suggestions and downloading the PDF use the real API (no model either), so it needs to be running.
      </p>
      <div className="scenario-tabs" role="group" aria-label="Sample scenario">
        {DEMO_SCENARIOS.map((s) => (
          <button key={s.id} type="button" aria-pressed={s.id === scenario.id} onClick={() => setScenarioId(s.id)}>
            {s.label}
          </button>
        ))}
      </div>
      {store.analysis && (
        <AnalysisView
          key={scenario.id}
          analysis={store.analysis}
          mainCv={scenario.cv}
          controls={{
            choose: () => {},
            changeFocus: () => {},
            decide: (action) => void store.decide(action),
            retry: () => {},
          }}
        />
      )}
    </section>
  );
}
