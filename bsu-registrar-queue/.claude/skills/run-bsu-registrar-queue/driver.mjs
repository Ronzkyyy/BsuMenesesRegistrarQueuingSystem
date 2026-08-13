// Minimal chromium-cli-style REPL for driving the BSU Registrar Queue frontend
// (Vite dev server) against the real FastAPI backend. See SKILL.md.
//
// Commands (one per stdin line):
//   nav <url>
//   wait-for <selector-or-text=...>
//   fill <selector> <value...>
//   select <selector> <value>
//   click <selector...>
//   press <key>
//   sleep <ms>
//   screenshot [name]
//   console
//   quit
//
// Screenshots land in ./screenshots/<name>.png (relative to cwd).

import { chromium } from 'playwright'
import readline from 'node:readline'
import path from 'node:path'
import fs from 'node:fs'

const screenshotDir = path.join(process.cwd(), 'screenshots')
fs.mkdirSync(screenshotDir, { recursive: true })

// This machine's cached Playwright browser build (chromium_headless_shell)
// doesn't match this Playwright version, so `chromium.launch()` with no
// channel fails with "Executable doesn't exist". `channel: 'chrome'` uses
// the system-installed Chrome instead and works everywhere Chrome is
// installed. See SKILL.md Gotchas.
const browser = await chromium.launch({ channel: 'chrome' })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

const consoleErrors = []
page.on('pageerror', (e) => consoleErrors.push(String(e)))
page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(msg.text())
})

let shotN = 0
const rl = readline.createInterface({ input: process.stdin })

for await (const line of rl) {
  const trimmed = line.trim()
  if (!trimmed || trimmed.startsWith('#')) continue
  const [cmd, ...rest] = trimmed.split(' ')
  try {
    if (cmd === 'nav') {
      await page.goto(rest[0], { waitUntil: 'networkidle' })
      console.log('OK nav', rest[0])
    } else if (cmd === 'wait-for') {
      const sel = rest.join(' ')
      await page.waitForSelector(sel, { timeout: 10000 })
      console.log('OK wait-for', sel)
    } else if (cmd === 'fill') {
      const sel = rest[0]
      const value = rest.slice(1).join(' ')
      await page.fill(sel, value)
      console.log('OK fill', sel)
    } else if (cmd === 'select') {
      const [sel, value] = rest
      await page.selectOption(sel, value)
      console.log('OK select', sel, value)
    } else if (cmd === 'click') {
      const sel = rest.join(' ')
      await page.click(sel)
      console.log('OK click', sel)
    } else if (cmd === 'press') {
      await page.keyboard.press(rest.join(' '))
      console.log('OK press')
    } else if (cmd === 'sleep') {
      await new Promise((r) => setTimeout(r, Number(rest[0] || 500)))
      console.log('OK sleep')
    } else if (cmd === 'screenshot') {
      const name = rest[0] || `shot-${++shotN}`
      const file = path.join(screenshotDir, `${name}.png`)
      await page.screenshot({ path: file })
      console.log('OK screenshot', file)
    } else if (cmd === 'console') {
      console.log('ERRORS', JSON.stringify(consoleErrors))
    } else if (cmd === 'quit') {
      break
    } else {
      console.log('ERR unknown command:', cmd)
    }
  } catch (e) {
    console.log('ERR', cmd, e.message.split('\n')[0])
  }
}

await browser.close()
process.exit(0)