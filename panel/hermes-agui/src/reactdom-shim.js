// Meme discipline d'acces paresseux que react-shim.js.
export function createRoot(...args) {
  return window.ReactDOM.createRoot(...args);
}
