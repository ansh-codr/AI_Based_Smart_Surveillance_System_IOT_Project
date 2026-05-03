#!/bin/bash
cd /home/pi/Desktop/IOT
set -a && . .env.example && set +a
echo "Starting AI Surveillance System..."
echo "Loading known faces..."
/home/pi/Desktop/IOT/.venv/bin/python app.py &
sleep 3
/home/pi/Desktop/IOT/.venv/bin/python monitor.py &

if command -v ngrok >/dev/null 2>&1; then
	if [[ -n "${NGROK_AUTHTOKEN:-}" ]]; then
		ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/tmp/ngrok_authtoken.log 2>&1 || true
	fi

	ngrok http https://127.0.0.1:5000 --log=stdout > /tmp/ngrok.log 2>&1 &
	sleep 2

	PUBLIC_URL=""
	for _ in $(seq 1 10); do
		for PORT in $(seq 4040 4050); do
			PUBLIC_URL=$(curl -s "http://localhost:${PORT}/api/tunnels" | python3 -c "import sys, json; d = json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null || true)
			if [[ -n "$PUBLIC_URL" ]]; then
				break
			fi
		done
		if [[ -n "$PUBLIC_URL" ]]; then
			break
		fi
		sleep 1
	done
	if [[ -n "$PUBLIC_URL" ]]; then
		echo "PUBLIC URL: $PUBLIC_URL"
		echo "Dashboard: $PUBLIC_URL/dashboard"
	else
		echo "ngrok started, but public URL not available yet. Check /tmp/ngrok.log"
	fi
else
	echo "ngrok is not installed. Local dashboard: https://$(hostname -I | cut -d' ' -f1):5000/dashboard"
fi
