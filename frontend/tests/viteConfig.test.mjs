import test from "node:test";
import assert from "node:assert/strict";

import config from "../vite.config.js";

test("the development proxy sends API requests to the Academic Agent backend", () => {
  assert.equal(config.server.proxy["/api"].target, "http://127.0.0.1:8010");
});
