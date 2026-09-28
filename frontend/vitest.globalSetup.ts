// frontend/vitest.globalSetup.ts
// Sets the timezone before any worker thread spawns so that V8 reads TZ at
// startup. This makes all Date locale methods (getFullYear, getDate, etc.)
// deterministic across machines and CI, matching the tests in utils.test.ts
// which assert America/New_York behavior.
export default function setup() {
  process.env.TZ = 'America/New_York'
}
