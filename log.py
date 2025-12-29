import sys

def _default_log_fn(data, *args, **kwargs):
    """默认日志函数：什么也不做"""
    pass

# 核心存储：使用模块属性确保全局共享
_module = sys.modules[__name__]

# 初始化日志函数
_module._log_fn = _default_log_fn

def log(data, *args, **kwargs):
    """
    日志输出函数 - 完全兼容原始API
    
    支持：
    - log("消息")
    - log("消息", style="red")  # 如果输出函数支持 kwargs
    - log(f"[bold]消息[/]")
    """
    try:
        # 如果data是字符串且有args，格式化
        if args and isinstance(data, str):
            try:
                data = data.format(*args)
            except:
                pass  # 如果格式化失败，保持原样
        
        # 调用当前日志函数
        _module._log_fn(data, *args, **kwargs)
    except Exception:
        # 如果日志函数出错，静默失败
        pass

def set_log_fn(fn):
    """
    设置日志函数 - 完全兼容原始API
    
    参数:
        fn: 输出函数，如 console.print、print 等
    """
    if not callable(fn):
        raise TypeError("日志函数必须是可调用的")
    
    # 保存到模块属性（全局共享）
    _module._log_fn = fn
    
    # 可选：测试输出
    try:
        fn("[dim]✅ 日志系统已初始化[/]")
    except:
        pass
