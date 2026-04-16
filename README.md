# SeewoStudentAnalysis

## 目录说明

- `app/`：后端服务（FastAPI）与识别入库逻辑
- `app/uploads/`：图片临时上传目录（运行时文件）
- `vue/`：前端静态页面
  - `index.html`：课堂列表 + 热力图展示
  - `admin.html`：图片入库页面

## 本地运行

1. 后端：
   - `cd /Users/shuijing/Documents/Code/SeewoStudentAnalysis/app`
   - `uvicorn main:app --reload --port 8000`
2. 前端（静态）：
   - `cd /Users/shuijing/Documents/Code/SeewoStudentAnalysis/vue`
   - `python3 -m http.server 4173`

## 备注

- 运行产生的缓存、IDE 配置和上传图片已通过 `.gitignore` 忽略。
