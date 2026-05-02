import "./styles/globals.css"
import React from "react"
import ReactDOM from "react-dom/client"
import { App } from "./app.js"
import { Providers } from "./providers.js"

async function bootstrap() {
  if (import.meta.env.DEV && import.meta.env["VITE_ENABLE_MOCK"] !== "false") {
    const { worker } = await import("./mocks/browser.js")
    await worker.start({ onUnhandledRequest: "bypass" }).catch(console.warn)
  } else if ("serviceWorker" in navigator) {
    const regs = await navigator.serviceWorker.getRegistrations()
    await Promise.all(regs.map((r) => r.unregister()))
  }

  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <Providers>
        <App />
      </Providers>
    </React.StrictMode>,
  )
}

void bootstrap()
