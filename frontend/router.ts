import { useEffect, useState } from "react";

export function navigate(to: string) {
  window.location.hash = to.startsWith("#") ? to : `#${to}`;
}

export function productPath(id: string, tab = "overview") {
  return `/products/${encodeURIComponent(id)}?tab=${tab}`;
}

export function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const onChange = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const raw = hash.replace(/^#/, "") || "/";
  const [path, queryString] = raw.split("?");
  return {
    hash,
    path,
    segments: path.split("/").filter(Boolean),
    params: new URLSearchParams(queryString || ""),
  };
}
