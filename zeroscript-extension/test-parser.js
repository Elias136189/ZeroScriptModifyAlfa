// Quick Node smoke test for core/parser.js (run: node test-parser.js). Not shipped.
const ZSParse = require("./core/parser.js");

const ok = (name, cond) => { console.log((cond ? "PASS" : "FAIL") + "  " + name); if (!cond) process.exitCode = 1; };

const paramless = ZSParse.parseToolCalls('{"command":"list_commands"}');
ok("paramless command", paramless.length === 1 && paramless[0].tool === "list_commands");

const braces = ZSParse.parseToolCalls('{"command":"multi_edit","params":{"code":"if x then {y} end"}}');
ok("braces inside string value", braces.length === 1 && braces[0].arguments.code === "if x then {y} end");

const legacy = ZSParse.parseToolCalls('{"tool":"pc_read","arguments":{"path":"src/main.js"}}');
ok("legacy tool/arguments schema", legacy.length === 1 && legacy[0].tool === "pc_read");

const mcp = ZSParse.parseToolCalls('###MCP_TOOL###\n{"command":"list_items"}\n###END_MCP_TOOL###');
ok("mcp_tool wrapper", mcp.length === 1 && mcp[0].tool === "list_items");

ok("open MCP block detected", ZSParse.hasOpenToolBlock('###MCP_TOOL###\n{"command":"list_items"') === true);
ok("closed MCP block not open", ZSParse.hasOpenToolBlock('###MCP_TOOL###\n{"command":"list_items"}\n###END_MCP_TOOL###') === false);
ok("open json command detected", ZSParse.hasOpenToolBlock('{"command":"multi_edit","params":{"a":1') === true);

ok("prose has no signature", ZSParse.hasToolSignature("Here is how you could use a command in theory.") === false);
ok("command shape detected", ZSParse.hasCommandShape('{"command":"x"}') === true);
ok("injected feedback detected", ZSParse.isInjectedFeedback("Output of 'list_items':\n[]") === true);
ok("parse-error note is feedback not command", ZSParse.isInjectedFeedback('ERROR: bad JSON, write {"command": "name"}') === true);
ok("tool name mid-stream", ZSParse.toolNameFromText('{"command":"multi_ed') === "multi_ed");

// ── salvageCutOff: auto-close a command whose trailing closers were cut ──
// The live Qwen case: a big multi_edit missing exactly ONE final "}".
const cut1 = ZSParse.salvageCutOff('{"command": "multi_edit", "params": {"file_path": "src/AdminHandler.js", "edits": [{"old_string": "a", "new_string": "b"}]}');
ok("salvage: one missing root brace", cut1 && cut1.tool === "multi_edit" && cut1.arguments.edits.length === 1);
// Two missing closers (params + root) still salvages.
const cut2 = ZSParse.salvageCutOff('{"command": "list_items", "params": {"verbose": true');
ok("salvage: two missing closers", cut2 && cut2.tool === "list_items" && cut2.arguments.verbose === true);
// Cut MID-STRING = real content amputated -> refuse.
ok("salvage refuses mid-string cut", ZSParse.salvageCutOff('{"command": "multi_edit", "params": {"edits": [{"old_string": "elseif command ==') === null);
// Deep deficit (cut between edits: ] } } missing = 3 closers) -> refuse.
ok("salvage refuses deep deficit", ZSParse.salvageCutOff('{"command": "multi_edit", "params": {"edits": [{"old_string": "a", "new_string": "b"}') === null);
// A CLOSED command is not salvage's business.
ok("salvage ignores closed command", ZSParse.salvageCutOff('{"command": "list_commands"}') === null);
// Dangling comma after the last complete value = incomplete next value -> refuse.
ok("salvage refuses trailing comma", ZSParse.salvageCutOff('{"command": "multi_edit", "params": {"edits": [{"old_string": "a"},') === null);
// Escaped quotes inside values must not confuse the string tracking.
const cutEsc = ZSParse.salvageCutOff('{"command": "list_items", "params": {"text": "quote: \\"hi\\""}');
ok("salvage handles escaped quotes", cutEsc && cutEsc.tool === "list_items" && cutEsc.arguments.text === 'quote: "hi"');

// ── DeepSeek's native DSML tool-call markup ────────────────────────────────
// DeepSeek sometimes answers in its own agentic markup instead of a ZeroScript
// command. It has no "command"/"tool" key and no ###...### markers, so the
// classify ladder used to miss it entirely and the turn died as plain text.
// DSML_RE is what fires the "dsml" parse_error that asks for a rewrite.
const dsmlFull = [
  '<|DSML|>tool_calls>',
  '<|DSML|>invoke name="pc_read">',
  '<|DSML|>parameter name="path" string="true">src/main.js</|DSML|>parameter>',
  '</|DSML|>invoke>',
  '</|DSML|>tool_calls>',
].join("\n");
ok("dsml full invoke block", ZSParse.DSML_RE.test(dsmlFull));
// The degenerate form seen in the wild: a bare opener and NO tool name at all -
// which is why the guard must not be gated on a known command name.
ok("dsml bare opener + prose",
   ZSParse.DSML_RE.test('<|DSML|>tool_calls>\n\n<section>Let me explore the remaining key services.</section>'));
// DeepSeek writes its special tokens with the FULL-WIDTH bar (U+FF5C).
ok("dsml full-width bar", ZSParse.DSML_RE.test('<｜DSML｜>invoke name="pc_read">'));
// The form as it appeared in user screenshots - doubled bars with spaces. The
// live capture (2026-08-22) showed DeepSeek actually emits plain ASCII bars and
// that this spacing is only the site's rendering, but the detector stays
// permissive so a build that really emits it is covered.
ok("dsml doubled bars with spaces", ZSParse.DSML_RE.test('< |  | DSML |  | tool_calls>'));
ok("dsml doubled-bar closer", ZSParse.DSML_RE.test('</ |  | DSML |  | parameter>'));
ok("dsml closing tag alone", ZSParse.DSML_RE.test('</|DSML|>parameter>'));
// DSML is NOT a ZeroScript command shape: it must reach the fallthrough guards.
ok("dsml is not a tool signature", !ZSParse.hasToolSignature(dsmlFull));
// DSML must NOT be a tool signature (it has to fall through to the classify
// ladder so the "dsml" parse_error fires) but it MUST be a command shape, so the
// camouflage sweep masks the raw markup behind a chip instead of showing it.
ok("dsml IS a command shape (so it gets masked)", ZSParse.hasCommandShape(dsmlFull));
ok("dsml bare opener is a command shape too", ZSParse.hasCommandShape('<|DSML|>tool_calls>'));
// No false positives: ordinary prose, a real command, and - critically - OUR OWN
// error note, which names DSML in words. If the note matched, the model echoing
// it would re-fire the error forever.
ok("no dsml false positive on prose",
   !ZSParse.DSML_RE.test("I considered the DSML invoke and parameter tags, but used JSON instead."));
ok("no dsml false positive on a real command",
   !ZSParse.DSML_RE.test('{"command": "pc_read", "params": {"path": "x"}}'));
