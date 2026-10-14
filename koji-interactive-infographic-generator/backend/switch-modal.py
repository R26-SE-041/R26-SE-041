"""From this backend folder, control EC2. Local routing requires --local explicitly."""
import sys

if "--local" in sys.argv:
    sys.argv.remove("--local")
    from studio.modal_accounts import main
else:
    from studio.modal_remote import main

arguments = sys.argv[1:]
if arguments and not arguments[0].startswith("-") and arguments[0] not in {"list", "status", "check", "switch", "rollback"}:
    arguments.insert(0, "switch")
raise SystemExit(main(arguments))
