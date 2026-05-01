import "./styles/globals.css"
import React from "react"
import ReactDOM from "react-dom/client"
import { App } from "./app.js"
import { Providers } from "./providers.js"

async function bootstrap() {
  if (import.meta.env.DEV) {
    const { worker } = await import("./mocks/browser.js")
    await worker.start({ onUnhandledRequest: "bypass" })
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
