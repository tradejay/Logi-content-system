"""Local console host using the same authoring API and dispatcher as the admin app."""
import argparse
from pathlib import Path
from flask import Flask, jsonify, send_from_directory
from services.content_ops_api import content_ops_bp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5014)
    args = parser.parse_args()
    static = Path(__file__).resolve().parents[1] / 'static'
    app = Flask(__name__, static_folder=str(static))
    app.register_blueprint(content_ops_bp)
    @app.get('/')
    def index():
        dist = static / 'dist'
        if (dist / 'index.html').exists():
            return send_from_directory(dist, 'index.html')
        return send_from_directory(static, 'article-console.html')

    @app.get('/app')
    def modern_app():
        dist = static / 'dist'
        if (dist / 'index.html').exists():
            return send_from_directory(dist, 'index.html')
        return send_from_directory(static, 'article-console.html')

    @app.get('/<path:filename>')
    def files(filename):
        dist = static / 'dist'
        if (static / filename).exists():
            return send_from_directory(static, filename)
        if (dist / filename).exists():
            return send_from_directory(dist, filename)
        return send_from_directory(static, filename)
    @app.get('/api/health')
    def health():
        return jsonify(status='ok', service='pipeline-console')
    app.run(host='127.0.0.1', port=args.port, threaded=True, debug=False)


if __name__ == '__main__':
    main()
