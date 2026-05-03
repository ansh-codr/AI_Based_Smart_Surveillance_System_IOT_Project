from iot_app import create_app


app = create_app()


if __name__ == "__main__":
    # Use adhoc SSL so getUserMedia works from remote browsers (self-signed cert is OK)
    app.run(host="0.0.0.0", port=5000, debug=False, ssl_context='adhoc')
