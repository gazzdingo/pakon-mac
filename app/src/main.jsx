import React from 'react';
import { createRoot } from 'react-dom/client';
import './theme.css';
import App from './App';
import { ErrorBoundary } from './components';

// The boundary is OUTSIDE StrictMode on purpose. StrictMode double-invokes
// render in development and re-throws caught errors so they reach devtools;
// the boundary sitting above it still catches, and in production — which is
// how this ships — it is the only thing between a render throw and a blank
// window.
createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <React.StrictMode>
      <App />
    </React.StrictMode>
  </ErrorBoundary>,
);
