# tools/decorators/debug.py
"""
调试装饰器：根据配置开关决定是否保存调试信息
"""
import logging
from functools import wraps
from typing import Callable
import config


def debug_save(save_type: str) -> Callable:
    """
    条件调试保存装饰器
    
    Args:
        save_type: 保存类型，'image' 或 'excel'
    
    Usage:
        @debug_save("image")
        def _save_debug_image(self, original_page, target_page, settings, page_num):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 根据配置决定是否执行
            if save_type == "image" and not config.ENABLE_DEBUG_IMAGE:
                return None
            if save_type == "excel" and not config.ENABLE_DEBUG_EXCEL:
                return None
            
            # 执行实际的保存逻辑
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
