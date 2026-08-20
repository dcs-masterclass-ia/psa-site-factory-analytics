// Ne bundle pas React : le runtime dc-runtime (support.js) le charge deja en
// global (window.React 18.3.1, UMD) pour le reste du dashboard -- on le
// reutilise pour ne pas embarquer une 2e copie de React dans la page.
//
// Acces paresseux (pas de destructuration au chargement du bundle) : ce
// script est charge en <script defer>, potentiellement avant que
// support.js n'ait fini de charger React lui-meme -- voir waitForReact()
// dans index.js, qui garantit que window.React existe avant tout appel
// aux fonctions ci-dessous.
export function createElement(...args) {
  return window.React.createElement(...args);
}
export function useState(...args) {
  return window.React.useState(...args);
}
export function useEffect(...args) {
  return window.React.useEffect(...args);
}
export function useRef(...args) {
  return window.React.useRef(...args);
}
export function useCallback(...args) {
  return window.React.useCallback(...args);
}
export function useMemo(...args) {
  return window.React.useMemo(...args);
}
export const ReactRef = {
  get Fragment() {
    return window.React.Fragment;
  },
};
