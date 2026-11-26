"""PyCharm 入口：右键本文件 → 运行 'run'。

工作目录默认就是 backend，所以 app 包可以直接导入。
启动后访问 http://localhost:8000/docs 查看接口文档。
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
