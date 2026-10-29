import { useState, useEffect } from "react";
import mermaid from "mermaid";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

const modules = [
  { id: "requirements", icon: "⌁", label: "Requirements" },
  { id: "stories", icon: "◈", label: "User Stories" },
  { id: "uml", icon: "⌘", label: "UML Studio" },
  { id: "database", icon: "▦", label: "Database" },
  { id: "apis", icon: "⇄", label: "API Design" },
  { id: "structure", icon: "⌂", label: "Architecture" },
  { id: "documentation", icon: "✦", label: "Documentation" },
];

const exampleRequirement = `Build an online food delivery platform where users can register and login, browse restaurants, view menus, add food items to their cart, place orders, make online payments and track deliveries.

Restaurant administrators should manage restaurants, menus, food items and incoming orders.

Delivery partners should view assigned deliveries and update delivery status.

The system should provide secure authentication, fast response times, reliable data storage and a responsive web interface.`;

function App() {
  const [requirements, setRequirements] = useState("");
  const [result, setResult] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    checkBackend();
  }, []);

  async function checkBackend() {
    try {
      const response = await fetch(`${API_URL}/health`);
      setConnected(response.ok);
    } catch {
      setConnected(false);
    }
  }

  async function generateSDLC() {
    if (!requirements.trim()) {
      setError("Describe your software idea first.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          requirements,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || `Server error: ${response.status}`
        );
      }

      setResult(data);
      setActiveTab("overview");
    } catch (err) {
      console.error(err);
      setError(
        err.message || "Unable to connect to the AI backend."
      );
    } finally {
      setLoading(false);
    }
  }

  function clearProject() {
    setRequirements("");
    setResult(null);
    setError("");
    setActiveTab("overview");
  }

  return (
    <div className="app">

      {/* BACKGROUND */}
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <div className="grid-background" />

      {/* SIDEBAR */}
      <aside className="sidebar">

        <div className="brand">
          <div className="brand-logo">
            <span>⌁</span>
          </div>

          <div>
            <div className="brand-name">SpecForge</div>
            <div className="brand-caption">AI SDLC ENGINE</div>
          </div>
        </div>

        <div className="sidebar-divider" />

        <div className="nav-title">
          WORKSPACE
        </div>

        <button
          className={`nav-item ${
            activeTab === "overview" ? "active" : ""
          }`}
          onClick={() => setActiveTab("overview")}
        >
          <span className="nav-icon">⌘</span>
          <span>Overview</span>
        </button>

        {modules.map((module) => (
          <button
            key={module.id}
            className={`nav-item ${
              activeTab === module.id ? "active" : ""
            }`}
            onClick={() => setActiveTab(module.id)}
          >
            <span className="nav-icon">
              {module.icon}
            </span>

            <span>{module.label}</span>

            {result && (
              <span className="nav-check">
                ✓
              </span>
            )}
          </button>
        ))}

        <div className="sidebar-bottom">

          <div className="engine-card">
            <div className="engine-orb">
              ✦
            </div>

            <div>
              <div className="engine-title">
                AI Engine
              </div>

              <div className="engine-status">
                <span />
                {connected
                  ? "Connected"
                  : "Offline"}
              </div>
            </div>
          </div>

          <div className="version">
            SPECFORGE v1.0
          </div>

        </div>

      </aside>

      {/* MAIN */}
      <main className="main">

        {/* TOP BAR */}
        <header className="topbar">

          <div className="breadcrumbs">
            <b>/</b>
           
          </div>

          <div className="top-actions">

            <div className="system-status">
              <span className={connected ? "online-dot" : "offline-dot"} />
              {connected ? "Backend online" : "Backend offline"}
            </div>

            {result && (
              <button
                className="new-project"
                onClick={clearProject}
              >
                + New Project
              </button>
            )}

          </div>

        </header>

        <div className="content">

          {/* HERO */}
          {!result && !loading && (
            <section className="hero">

              <div className="hero-left">

                <div className="ai-pill">
                  <span className="spark">✦</span>
                  AI-POWERED SOFTWARE ARCHITECT
                  <span className="pill-live">
                    LIVE
                  </span>
                </div>
                <h2>SPEC FORGE</h2>
                <h1>
                  Turn ideas into
                  <br />
                  <span>complete software blueprints.</span>
                </h1>

                <p>
                  Describe your software idea. SpecForge
                  transforms it into requirements, user stories,
                  UML, database architecture, APIs, project
                  structure and documentation.
                </p>

                <div className="hero-stats">

                  <div>
                    <strong>7</strong>
                    <span>SDLC modules</span>
                  </div>

                  <div>
                    <strong>AI</strong>
                    <span>Architecture engine</span>
                  </div>

                  <div>
                    <strong>∞</strong>
                    <span>Project possibilities</span>
                  </div>

                </div>

              </div>

              <div className="hero-visual">

                <div className="orbit orbit-a" />
                <div className="orbit orbit-b" />
                <div className="orbit orbit-c" />

                <div className="core">

                  <div className="core-glow" />

                  <span>✦</span>

                  <small>AI</small>

                </div>

                <div className="floating-node node-one">
                  <span>⌁</span>
                  REQ
                </div>

                <div className="floating-node node-two">
                  <span>⌘</span>
                  UML
                </div>

                <div className="floating-node node-three">
                  <span>▦</span>
                  DB
                </div>

                <div className="floating-node node-four">
                  <span>⇄</span>
                  API
                </div>

              </div>

            </section>
          )}

          {/* INPUT */}
          {!result && !loading && (
            <section className="workspace-card">

              <div className="workspace-header">

                <div>
                  <div className="section-eyebrow">
                    PROJECT INPUT
                  </div>

                  <h2>
                    What are you building?
                  </h2>

                  <p>
                    Start with a product idea, requirements,
                    or a rough system description.
                  </p>
                </div>

                <button
                  className="example-button"
                  onClick={() =>
                    setRequirements(exampleRequirement)
                  }
                >
                  ✦ Use example
                </button>

              </div>

              <div className="textarea-wrapper">

                <textarea
                  value={requirements}
                  onChange={(e) =>
                    setRequirements(e.target.value)
                  }
                  placeholder={`Describe your software project...

Example:
Build an online food delivery platform where users can register, browse restaurants, add food to cart, place orders and track deliveries.`}
                />

                <div className="textarea-glow" />

                <div className="input-meta">

                  <span>
                    {requirements.length} characters
                  </span>

                  <span>
                    AI will analyze your requirements
                  </span>

                </div>

              </div>

              {error && (
                <div className="error-box">
                  <span>⚠</span>
                  {error}
                </div>
              )}

              <div className="generate-row">

                <div className="pipeline-mini">

                  {modules.slice(0, 5).map((module, index) => (
                    <div
                      className="mini-module"
                      key={module.id}
                    >
                      <span>{module.icon}</span>

                      {index < 4 && (
                        <i />
                      )}
                    </div>
                  ))}

                  <span className="pipeline-more">
                    +2
                  </span>

                </div>

                <button
                  className="generate-button"
                  onClick={generateSDLC}
                  disabled={loading}
                >

                  {loading ? (
                    <>
                      <span className="spinner" />
                      Generating blueprint...
                    </>
                  ) : (
                    <>
                      Generate SDLC
                      <span>→</span>
                    </>
                  )}

                </button>

              </div>

            </section>
          )}

          {/* LOADING */}
          {loading && (
            <LoadingScreen />
          )}

          {/* RESULT */}
          {result && !loading && (
            <ResultWorkspace
              result={result}
              activeTab={activeTab}
              setActiveTab={setActiveTab}
              clearProject={clearProject}
            />
          )}

        </div>

      </main>

    </div>
  );
}


/* =========================================================
   LOADING SCREEN
========================================================= */

function LoadingScreen() {

  const steps = [
    "Parsing requirements",
    "Extracting system actors",
    "Building user stories",
    "Designing database",
    "Generating APIs",
    "Creating UML architecture",
    "Preparing documentation",
  ];

  return (
    <div className="loading-screen">

      <div className="loading-orb">

        <div className="loading-ring ring-one" />
        <div className="loading-ring ring-two" />
        <div className="loading-ring ring-three" />

        <div className="loading-core">
          ✦
        </div>

      </div>

      <div className="loading-title">
        Architecting your system
      </div>

      <p>
        AI is transforming your requirements into
        an end-to-end software blueprint.
      </p>

      <div className="loading-steps">

        {steps.map((step, index) => (

          <div
            className="loading-step"
            key={step}
            style={{
              animationDelay: `${index * 0.15}s`,
            }}
          >
            <span>
              {index + 1}
            </span>

            {step}

          </div>

        ))}

      </div>

    </div>
  );
}


/* =========================================================
   RESULT WORKSPACE
========================================================= */

function ResultWorkspace({
  result,
  activeTab,
  setActiveTab,
  clearProject,
}) {

  const project =
    result.project || {};

  const requirementAnalysis =
    result.requirement_analysis || {};

  const stories =
    result.user_stories || [];

  const database =
    result.database || {};

  const apis =
    result.apis || [];

  const projectStructure =
    result.project_structure || {};

  return (
    <div className="result-workspace">

      {/* RESULT HEADER */}

      <div className="result-header">

        <div>

          <div className="result-badge">
            <span>✦</span>
            BLUEPRINT GENERATED
          </div>

          <h1>
            {project.name || "Software Blueprint"}
          </h1>

          <p>
            {project.summary ||
              "Your complete SDLC architecture is ready."}
          </p>

        </div>

        <button
          className="new-project large"
          onClick={clearProject}
        >
          + New project
        </button>

      </div>

      {/* METRICS */}

      <div className="metrics">

        <Metric
          value={
            requirementAnalysis
              .functional_requirements?.length || 0
          }
          label="Requirements"
          icon="⌁"
        />

        <Metric
          value={stories.length}
          label="User Stories"
          icon="◈"
        />

        <Metric
          value={database.tables?.length || 0}
          label="Tables"
          icon="▦"
        />

        <Metric
          value={apis.length}
          label="API Endpoints"
          icon="⇄"
        />

      </div>

      {/* TAB BAR */}

      <div className="result-tabs">

        <button
          className={activeTab === "overview" ? "active" : ""}
          onClick={() => setActiveTab("overview")}
        >
          Overview
        </button>

        {modules.map((module) => (

          <button
            key={module.id}
            className={
              activeTab === module.id
                ? "active"
                : ""
            }
            onClick={() =>
              setActiveTab(module.id)
            }
          >
            {module.icon}
            {module.label}
          </button>

        ))}

      </div>

      {/* CONTENT */}

      {activeTab === "overview" && (
        <Overview
          result={result}
          requirementAnalysis={requirementAnalysis}
          stories={stories}
          database={database}
          apis={apis}
          projectStructure={projectStructure}
          setActiveTab={setActiveTab}
        />
      )}

      {activeTab === "requirements" && (
        <Requirements data={requirementAnalysis} />
      )}

      {activeTab === "stories" && (
        <UserStories stories={stories} />
      )}

      {activeTab === "uml" && (
        <UML result={result.uml || {}} />
      )}

      {activeTab === "database" && (
        <Database data={database} />
      )}

      {activeTab === "apis" && (
        <APIs apis={apis} />
      )}

      {activeTab === "structure" && (
        <ProjectStructure data={projectStructure} />
      )}

      {activeTab === "documentation" && (
        <Documentation
          documentation={result.documentation || {}}
        />
      )}

    </div>
  );
}


/* =========================================================
   METRIC
========================================================= */

function Metric({ value, label, icon }) {

  return (
    <div className="metric">

      <div className="metric-icon">
        {icon}
      </div>

      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>

    </div>
  );
}


/* =========================================================
   OVERVIEW
========================================================= */

function Overview({
  result,
  requirementAnalysis,
  stories,
  database,
  apis,
  projectStructure,
  setActiveTab,
}) {

  return (
    <div className="overview-grid">

      <div className="overview-main">

        <div className="section-card">

          <div className="card-heading">
            <div>
              <span>01</span>
              <h3>System understanding</h3>
            </div>

            <button
              onClick={() =>
                setActiveTab("requirements")
              }
            >
              Explore →
            </button>
          </div>

          <p className="overview-summary">
            {result.project?.summary ||
              "AI-generated system analysis."}
          </p>

          <div className="actor-row">

            {(requirementAnalysis.actors || [])
              .slice(0, 5)
              .map((actor) => (

                <div
                  className="actor-pill"
                  key={actor.name}
                >
                  <span>●</span>
                  {actor.name}
                </div>

              ))}

          </div>

        </div>

        <div className="section-card">

          <div className="card-heading">
            <div>
              <span>02</span>
              <h3>SDLC pipeline</h3>
            </div>
          </div>

          <div className="pipeline">

            {modules.map((module, index) => (

              <button
                key={module.id}
                className="pipeline-card"
                onClick={() =>
                  setActiveTab(module.id)
                }
              >

                <div className="pipeline-number">
                  0{index + 1}
                </div>

                <div className="pipeline-icon">
                  {module.icon}
                </div>

                <strong>
                  {module.label}
                </strong>

                <small>
                  Generated
                </small>

                {index < modules.length - 1 && (
                  <div className="pipeline-arrow">
                    →
                  </div>
                )}

              </button>

            ))}

          </div>

        </div>

      </div>

      <div className="overview-side">

        <div className="insight-card">

          <div className="insight-icon">
            ✦
          </div>

          <span>AI ARCHITECTURE INSIGHT</span>

          <h3>
            Your system is ready for implementation.
          </h3>

          <p>
            Requirements have been transformed into
            a structured development blueprint covering
            architecture, data, APIs and delivery.
          </p>

        </div>

        <div className="quick-card">

          <div className="quick-title">
            BLUEPRINT HEALTH
          </div>

          <HealthRow
            label="Requirements"
            value={
              requirementAnalysis
                .functional_requirements?.length || 0
            }
          />

          <HealthRow
            label="Stories"
            value={stories.length}
          />

          <HealthRow
            label="Database"
            value={database.tables?.length || 0}
          />

          <HealthRow
            label="APIs"
            value={apis.length}
          />

          <HealthRow
            label="Tech stack"
            value={
              projectStructure
                .technology_stack?.length || 0
            }
          />

        </div>

      </div>

    </div>
  );
}


function HealthRow({ label, value }) {

  return (
    <div className="health-row">

      <span>{label}</span>

      <div className="health-value">
        <i />
        {value}
      </div>

    </div>
  );
}


/* =========================================================
   REQUIREMENTS
========================================================= */

function Requirements({ data }) {

  return (
    <div className="content-grid">

      <section className="section-card wide">

        <div className="card-heading">
          <div>
            <span>01</span>
            <h3>Functional requirements</h3>
          </div>
        </div>

        <div className="requirement-grid">

          {(data.functional_requirements || [])
            .map((item, index) => (

              <div
                className="requirement-card"
                key={index}
              >

                <span>
                  FR-{String(index + 1).padStart(2, "0")}
                </span>

                <p>{item}</p>

              </div>

            ))}

        </div>

      </section>

      <section className="section-card">

        <div className="card-heading">
          <div>
            <span>02</span>
            <h3>Non-functional</h3>
          </div>
        </div>

        <ul className="clean-list">

          {(data.non_functional_requirements || [])
            .map((item, index) => (

              <li key={index}>
                <span>✦</span>
                {item}
              </li>

            ))}

        </ul>

      </section>

      <section className="section-card">

        <div className="card-heading">
          <div>
            <span>03</span>
            <h3>System actors</h3>
          </div>
        </div>

        <div className="actor-grid-new">

          {(data.actors || []).map((actor) => (

            <div
              className="actor-card-new"
              key={actor.name}
            >
              <div>◉</div>

              <strong>
                {actor.name}
              </strong>

              <p>
                {actor.description}
              </p>

            </div>

          ))}

        </div>

      </section>

      <section className="section-card wide">

        <div className="card-heading">
          <div>
            <span>04</span>
            <h3>Use cases</h3>
          </div>
        </div>

        <div className="usecase-grid-new">

          {(data.use_cases || []).map(
            (useCase, index) => (

              <div
                className="usecase-card-new"
                key={index}
              >

                <div className="usecase-number">
                  {String(index + 1).padStart(2, "0")}
                </div>

                <div>

                  <strong>
                    {useCase.name}
                  </strong>

                  <span>
                    {useCase.actor}
                  </span>

                  <p>
                    {useCase.description}
                  </p>

                </div>

              </div>

            )
          )}

        </div>

      </section>

    </div>
  );
}


/* =========================================================
   USER STORIES
========================================================= */

function UserStories({ stories }) {

  return (
    <div className="stories-grid">

      {stories.map((story, index) => (

        <article
          className="story-card-new"
          key={story.id || index}
        >

          <div className="story-header">

            <span className="story-number">
              {story.id ||
                `US-${String(index + 1).padStart(3, "0")}`}
            </span>

            <div className="story-tags">

              <span
                className={`priority ${
                  (story.priority || "")
                    .toLowerCase()
                }`}
              >
                {story.priority || "Medium"}
              </span>

              <span className="points">
                {story.story_points || 3} pts
              </span>

            </div>

          </div>

          <p className="story-text">
            {story.story}
          </p>

          <div className="story-footer">

            <span>
              ◷ {story.sprint || "Sprint 1"}
            </span>

            <span>
              {story.acceptance_criteria?.length || 0}
              {" "}criteria
            </span>

          </div>

          {story.acceptance_criteria?.length > 0 && (

            <div className="criteria">

              <small>
                ACCEPTANCE CRITERIA
              </small>

              {story.acceptance_criteria.map(
                (criterion, i) => (

                  <div key={i}>
                    <span>✓</span>
                    {criterion}
                  </div>

                )
              )}

            </div>

          )}

        </article>

      ))}

    </div>
  );
}


/* =========================================================
   UML
========================================================= */

function UML({ result }) {

  return (
    <div className="uml-page">

      <div className="uml-header">

        <div>
          <div className="section-eyebrow">
            ARCHITECTURE VISUALIZER
          </div>

          <h2>
            UML Studio
          </h2>

          <p>
            AI-generated architecture diagrams.
          </p>
        </div>

      </div>

      <DiagramCard
        title="Use Case Diagram"
        icon="◉"
        chart={result.use_case}
      />

      <DiagramCard
        title="Class Diagram"
        icon="⌘"
        chart={result.class_diagram}
      />

      <DiagramCard
        title="Sequence Diagram"
        icon="⇄"
        chart={result.sequence}
      />

    </div>
  );
}


function DiagramCard({
  title,
  icon,
  chart,
}) {

  return (
    <div className="diagram-card">

      <div className="diagram-title">

        <div className="diagram-icon">
          {icon}
        </div>

        <div>
          <strong>{title}</strong>
          <span>AI generated</span>
        </div>

      </div>

      <MermaidDiagram chart={chart} />

    </div>
  );
}


function MermaidDiagram({ chart }) {

  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {

    async function render() {

      if (!chart) {
        setError("Diagram unavailable.");
        return;
      }

      try {

        setError("");

        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          securityLevel: "loose",
          fontFamily: "DM Sans",
        });

        let clean = chart
          .replace(/\\n/g, "\n")
          .replace(/```mermaid/gi, "")
          .replace(/```/g, "")
          .trim();

        const id =
          "diagram-" +
          Math.random()
            .toString(36)
            .substring(2, 9);

        const rendered =
          await mermaid.render(id, clean);

        setSvg(rendered.svg);

      } catch (err) {

        console.error(err);

        setError(
          "Unable to render this diagram."
        );

      }
    }

    render();

  }, [chart]);

  if (error) {
    return (
      <div className="diagram-error">
        ⚠ {error}
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="diagram-loading">
        Rendering architecture...
      </div>
    );
  }

  return (
    <div
      className="diagram-svg"
      dangerouslySetInnerHTML={{
        __html: svg,
      }}
    />
  );
}


/* =========================================================
   DATABASE
========================================================= */

function Database({ data }) {

  return (
    <div className="database-page">

      <div className="section-card">

        <div className="card-heading">
          <div>
            <span>01</span>
            <h3>Relational schema</h3>
          </div>

          <span className="valid-badge">
            ✓ {data.validation?.sql_syntax || "Validated"}
          </span>

        </div>

        <div className="table-grid">

          {(data.tables || []).map((table) => (

            <div
              className="schema-card-new"
              key={table.table}
            >

              <div className="schema-title">
                <div className="database-icon">
                  ▦
                </div>

                <strong>
                  {table.table}
                </strong>

              </div>

              <div className="columns">

                {(table.columns || []).map(
                  (column) => (

                    <div
                      className="column"
                      key={column.name}
                    >

                      <span>
                        {column.primary_key && (
                          <b>PK</b>
                        )}

                        {column.foreign_key && (
                          <i>FK</i>
                        )}

                        {column.name}
                      </span>

                      <small>
                        {column.type}
                      </small>

                    </div>

                  )
                )}

              </div>

            </div>

          ))}

        </div>

      </div>

      <div className="section-card">

        <div className="card-heading">

          <div>
            <span>02</span>
            <h3>Relationships</h3>
          </div>

          <span className="valid-badge">
            {data.validation?.semantic || "Validated"}
          </span>

        </div>

        <div className="relationship-list">

          {(data.relationships || []).map(
            (relationship, index) => (

              <div
                className="relationship"
                key={index}
              >

                <strong>
                  {relationship.from}
                </strong>

                <span>
                  {relationship.cardinality}
                </span>

                <strong>
                  {relationship.to}
                </strong>

                <p>
                  {relationship.description}
                </p>

              </div>

            )
          )}

        </div>

      </div>

      <div className="section-card">

        <div className="card-heading">
          <div>
            <span>03</span>
            <h3>SQL DDL</h3>
          </div>
        </div>

        <pre className="code-block">
          {data.sql || "No SQL generated."}
        </pre>

      </div>

    </div>
  );
}


/* =========================================================
   APIS
========================================================= */

function APIs({ apis }) {

  return (
    <div className="api-grid-new">

      {apis.map((api, index) => (

        <div
          className="api-card-new"
          key={index}
        >

          <div className="api-card-top">

            <span
              className={`method ${(
                api.method || "GET"
              ).toLowerCase()}`}
            >
              {api.method}
            </span>

            <span>
              API-{String(index + 1).padStart(2, "0")}
            </span>

          </div>

          <code>
            {api.endpoint}
          </code>

          <p>
            {api.purpose}
          </p>

          <div className="api-statuses">

            {(api.status_codes || []).map(
              (status) => (

                <span key={status.code}>
                  {status.code}
                </span>

              )
            )}

          </div>

          <div className="api-io">

            <div>
              <small>REQUEST</small>
              <pre>
                {JSON.stringify(
                  api.request_body || {},
                  null,
                  2
                )}
              </pre>
            </div>

            <div>
              <small>RESPONSE</small>
              <pre>
                {JSON.stringify(
                  api.response_body || {},
                  null,
                  2
                )}
              </pre>
            </div>

          </div>

        </div>

      ))}

    </div>
  );
}


/* =========================================================
   PROJECT STRUCTURE
========================================================= */

function ProjectStructure({ data }) {

  return (
    <div className="structure-page">

      <div className="stack-grid-new">

        {(data.technology_stack || []).map(
          (item, index) => (

            <div
              className="tech-card"
              key={index}
            >

              <span>
                {item.category}
              </span>

              <strong>
                {item.technology}
              </strong>

              <p>
                {item.reason}
              </p>

            </div>

          )
        )}

      </div>

      <div className="structure-columns">

        <div className="section-card">

          <div className="card-heading">
            <div>
              <span>01</span>
              <h3>Architecture</h3>
            </div>
          </div>

          <div className="architecture-box">
            {data.architecture}
          </div>

        </div>

        <div className="section-card">

          <div className="card-heading">
            <div>
              <span>02</span>
              <h3>Dependencies</h3>
            </div>
          </div>

          <div className="dependency-list">

            {(data.dependencies || []).map(
              (dependency) => (
                <span key={dependency}>
                  {dependency}
                </span>
              )
            )}

          </div>

        </div>

      </div>

      <div className="section-card">

        <div className="card-heading">
          <div>
            <span>03</span>
            <h3>Project structure</h3>
          </div>
        </div>

        <div className="file-tree-new">

          {(data.folders || []).map(
            (folder, index) => (

              <div
                key={index}
                style={{
                  paddingLeft:
                    `${(folder.match(/\//g) || []).length * 18}px`,
                }}
              >
                <span>
                  {folder.endsWith("/")
                    ? "▾"
                    : "•"}
                </span>

                {folder}
              </div>

            )
          )}

        </div>

      </div>

    </div>
  );
}


/* =========================================================
   DOCUMENTATION
========================================================= */

function Documentation({
  documentation,
}) {

  const sections = [
    ["README", documentation.readme],
    ["API Documentation", documentation.api_documentation],
    ["Installation", documentation.installation],
    ["Deployment", documentation.deployment],
    ["Sprint Plan", documentation.sprint_plan],
    ["Architecture", documentation.architecture],
  ];

  return (
    <div className="documentation-grid">

      {sections.map(([title, content]) => (

        <div
          className="doc-card"
          key={title}
        >

          <div className="doc-header">

            <span>✦</span>

            <strong>
              {title}
            </strong>

          </div>

          <pre>
            {content || "Not generated."}
          </pre>

        </div>

      ))}

    </div>
  );
}

export default App;