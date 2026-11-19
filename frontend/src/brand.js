// The product name lives here ONLY (frontend). Backend: backend/app/config.py DEFAULT_APP_NAME.
// Finalists: Groundwork / Commissary Club. Override at build time with VITE_APP_NAME.
export const APP_NAME = import.meta.env.VITE_APP_NAME || "Groundwork";

// The sibling site (young entrepreneurs) shown in the welcome banner's parade.
// Like APP_NAME, this is the only place the name is written. Override at build time.
export const SIBLING_NAME = import.meta.env.VITE_SIBLING_NAME || "Groundwork YEE";
