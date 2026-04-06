/**
 * useDebounce Hook
 * 防抖Hook，延迟更新值
 */

import { useState, useEffect } from 'react';

/**
 * useDebounce Hook
 * @param value - 需要防抖的值
 * @param delay - 延迟时间（毫秒）
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    // 设置定时器
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    // 清理函数：在value变化或组件卸载时清除定时器
    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

export default useDebounce;
