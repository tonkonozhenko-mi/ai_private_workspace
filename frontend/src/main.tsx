import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
// Legacy styles are kept underneath during the staged UI cleanup. The clean
// stylesheet is imported last so its rules win as each section is rewritten.
// Once every section is migrated, styles.legacy.css and this import are removed.
import "./styles.legacy.css";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
