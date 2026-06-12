from __future__ import annotations

from policy_index.api import create_app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5065, debug=True)
