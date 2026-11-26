"""检查 TensorRT 运行条件：右键 → 运行 'check_gpu'。逐项打印，哪一项失败就先解决哪一项。"""
import importlib
import sys

ok = True


def item(name, fn):
    global ok
    try:
        print(f"[通过] {name}：{fn()}")
    except Exception as exc:
        ok = False
        print(f"[失败] {name}：{exc.__class__.__name__}: {exc}")


print("Python", sys.version.split()[0], sys.executable)
torch = importlib.import_module("torch")
item("PyTorch", lambda: torch.__version__)
item("CUDA 可用", lambda: torch.cuda.is_available() or (_ for _ in ()).throw(RuntimeError("安装的是 CPU 版 torch，请按 README 安装 cu128 版")))
item("显卡", lambda: f"{torch.cuda.get_device_name(0)}，算力 sm_{''.join(map(str, torch.cuda.get_device_capability(0)))}")
item("PyTorch 支持此显卡", lambda: (torch.zeros(1, device="cuda") + 1).item())
item("TensorRT", lambda: importlib.import_module("tensorrt").__version__)
item("ONNX", lambda: importlib.import_module("onnx").__version__)
item("Ultralytics", lambda: importlib.import_module("ultralytics").__version__)
print("\n全部通过，可以运行 build_engine.py" if ok else "\n有失败项，解决后再运行 build_engine.py")
