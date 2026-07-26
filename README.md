# Note Digger — AI 自动钢琴扒谱

将音频录音自动转录为高质量钢琴五线谱。

## 快速启动

### 前置条件
- Docker & Docker Compose
- Python 3.11+ (本地开发)
- Node.js 18+ (前端开发)

### 一键启动（Docker）
```bash
cp .env.example .env
docker-compose up -d
```

访问 http://localhost:8000

### 本地开发

#### 后端
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 启动 Redis（需要单独安装或用 Docker）
docker run -d -p 6379:6379 redis:7-alpine

# 启动 Celery worker
celery -A app.tasks.celery_app worker --loglevel=info

# 启动 FastAPI
uvicorn app.main:app --reload --port 8000
```

#### 前端
```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

## API 文档
启动后端后访问 http://localhost:8000/docs 查看 Swagger 文档。

## 技术栈
- **AI**: Aria-AMT (EleutherAI) — 钢琴转录
- **后端**: FastAPI + Celery + Redis
- **前端**: Next.js + React + OpenSheetMusicDisplay
- **部署**: Docker Compose

## License
MIT
