from pathlib import Path
import argparse
import json
import sys
import time
import uuid


def main():
	args = _args()
	code = _read_code(args)
	request_id = args.id or time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
	queue = Path(args.queue).expanduser()
	request_dir = queue / "requests"
	response_dir = queue / "responses"
	request_dir.mkdir(parents=True, exist_ok=True)
	response_dir.mkdir(parents=True, exist_ok=True)

	request = {
		"id": request_id,
		"mode": "eval" if args.eval else "exec",
		"created": time.time(),
		"code": code,
	}
	tmp_path = request_dir / "{}.tmp".format(request_id)
	request_path = request_dir / "{}.json".format(request_id)
	tmp_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
	tmp_path.replace(request_path)

	if args.no_wait:
		print(str(request_path))
		return 0
	response = _wait_for_response(response_dir / "{}.json".format(request_id), args.timeout)
	print(json.dumps(response, indent=2))
	return 0 if response.get("ok") else 1


def _args():
	parser = argparse.ArgumentParser(description="Send Python to the TouchDesigner CodexDebugger.")
	parser.add_argument("--queue", default=str(Path.home() / "td_scripts" / "debug" / "codex_debugger" / "queue"))
	parser.add_argument("--code", default="")
	parser.add_argument("--file", default="")
	parser.add_argument("--id", default="")
	parser.add_argument("--eval", action="store_true", help="Evaluate code as an expression.")
	parser.add_argument("--timeout", type=float, default=10.0)
	parser.add_argument("--no-wait", action="store_true")
	return parser.parse_args()


def _read_code(args):
	if args.file:
		return Path(args.file).read_text(encoding="utf-8")
	if args.code:
		return args.code
	if not sys.stdin.isatty():
		return sys.stdin.read()
	raise SystemExit("Provide --code, --file, or stdin.")


def _wait_for_response(path, timeout):
	deadline = time.time() + timeout
	while time.time() < deadline:
		if path.exists():
			return json.loads(path.read_text(encoding="utf-8"))
		time.sleep(0.05)
	return {
		"ok": False,
		"error": "Timed out waiting for TouchDesigner response at {}".format(path),
	}


if __name__ == "__main__":
	raise SystemExit(main())
