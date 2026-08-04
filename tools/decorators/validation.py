# tools/decorators/validation.py
"""
参数验证装饰器：验证输入参数的合法性
"""
import logging
import pandas as pd
from functools import wraps
from typing import Callable


def validate_dataframe(allow_empty: bool = False) -> Callable:
    """
    验证 DataFrame 参数的装饰器
    
    Args:
        allow_empty: 是否允许空 DataFrame
    
    Usage:
        @validate_dataframe(allow_empty=False)
        def clean_cell_newlines(df: pd.DataFrame) -> pd.DataFrame:
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 获取 DataFrame 参数（假设是第一个参数或名为 'df' 的关键字参数）
            df = None
            if args and len(args) > 0:
                df = args[0]
            elif 'df' in kwargs:
                df = kwargs['df']
            
            # 验证 DataFrame
            if df is None:
                raise ValueError(f"{func.__name__}: DataFrame 不能为 None")
            
            if not isinstance(df, pd.DataFrame):
                raise TypeError(f"{func.__name__}: 参数必须是 DataFrame，当前类型: {type(df)}")
            
            if not allow_empty and df.empty:
                logging.warning(f"⚠️ {func.__name__}: 收到空 DataFrame，直接返回")
                return df
            
            # 执行函数
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
