# tools/decorators/logging.py
"""
日志装饰器：自动记录函数调用和参数
"""
import logging
from functools import wraps
from typing import Callable


def log_execution(level: int = logging.DEBUG, log_args: bool = False) -> Callable:
    """
    记录函数执行日志的装饰器
    
    Args:
        level: 日志级别 (logging.DEBUG, logging.INFO, 等)
        log_args: 是否记录参数
    
    Usage:
        @log_execution(level=logging.INFO)
        def clean_cell_newlines(df):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 构建函数调用信息
            func_info = f"{func.__name__}"
            
            if log_args:
                # 跳过 self 参数（args[0]）
                args_repr = [repr(a) for a in args[1:]] if len(args) > 1 else []
                kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
                all_args = ", ".join(args_repr + kwargs_repr)
                func_info += f"({all_args})"
            
            logging.log(level, f"🔧 调用 {func_info}")
            
            try:
                result = func(*args, **kwargs)
                logging.log(level, f"✅ {func.__name__} 执行完成")
                return result
            except Exception as e:
                logging.log(level, f"❌ {func.__name__} 执行异常: {e}")
                raise
        
        return wrapper
    return decorator
