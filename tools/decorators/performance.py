# tools/decorators/performance.py
"""
性能监控装饰器：监控函数执行时间
"""
import time
import logging
from functools import wraps
from typing import Optional, Callable


def timing_decorator(step_name: Optional[str] = None) -> Callable:
    """
    监控函数执行时间的装饰器
    
    Args:
        step_name: 步骤名称，如果为 None 则使用函数名
    
    Usage:
        @timing_decorator("数据清洗")
        def clean_data(self, tables, page_num):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = step_name or func.__name__
            start = time.time()
            
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                logging.info(f"⏱️  [{name}] 耗时: {elapsed:.3f}秒")
                return result
            except Exception as e:
                elapsed = time.time() - start
                logging.error(f"⏱️  [{name}] 执行失败 (耗时: {elapsed:.3f}秒)")
                raise
        
        return wrapper
    return decorator
