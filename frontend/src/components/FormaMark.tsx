import React, { useId } from "react";

export function FormaMark() {
  const gradient = useId();
  return <svg className="forma-symbol" viewBox="0 0 48 48" fill="none" aria-hidden="true">
    <defs><linearGradient id={gradient} x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
      <stop stopColor="#B66BFF"/><stop offset=".52" stopColor="#618BFF"/><stop offset="1" stopColor="#23D2E5"/>
    </linearGradient></defs>
    <path d="M11 38V14C11 10.7 13.7 8 17 8H37M11 24H29" stroke={`url(#${gradient})`} strokeWidth="8" strokeLinecap="round"/>
  </svg>;
}
