# tools/decorators/error_handling.py
"""
异常处理装饰器：统一处理异常，提供降级方案
"""
import logging
from functools import wraps
from typing import Any, Callable, Optional


def safe_execute(default_return: Any = None, log_error: bool = True) -> Callable:
    """
    安全执行装饰器，捕获异常并返回默认值
    
    Args:
        default_return: 发生异常时的默认返回值
        log_error: 是否记录错误日志
    
    Usage:
        @safe_execute(default_return=None)
        def locate_roi(self, page):
            pass
            
        @safe_execute(default_return=pd.DataFrame())
        def clean_data(self, tables, page_num):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    # 获取类名（如果是方法调用）
                    class_name = ""
                    if args and hasattr(args[0], '__class__'):
                        class_name = f"{args[0].__class__.__name__}."
                    
                    logging.error(
                        f"❌ {class_name}{func.__name__} 执行失败: {e}",
                        exc_info=True
                    )
                
                return default_return
        
        return wrapper
    return decorator
