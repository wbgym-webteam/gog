from app import create_app, socketio

app = create_app()

# For Gunicorn with eventlet worker
# The app needs to be wrapped with socketio for WebSocket support
application = socketio.wsgi_app(app)

if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000)