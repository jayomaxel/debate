import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { DebateVisibility, LobbyRoomStatus, LobbySort } from '@/services/student.service';
import { Search } from 'lucide-react';

export interface LobbyFilterValue {
  keyword: string;
  visibility: DebateVisibility | 'all';
  status: LobbyRoomStatus | 'all';
  occupancy: 'all' | 'available' | 'almost_full';
  sort: LobbySort;
}

interface DebateLobbyFilterProps {
  value: LobbyFilterValue;
  onChange: (value: LobbyFilterValue) => void;
  onReset: () => void;
}

const DebateLobbyFilter: React.FC<DebateLobbyFilterProps> = ({ value, onChange, onReset }) => {
  const update = <K extends keyof LobbyFilterValue>(key: K, nextValue: LobbyFilterValue[K]) => {
    onChange({ ...value, [key]: nextValue });
  };

  return (
    <div className='grid gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm lg:grid-cols-[minmax(220px,1fr)_160px_160px_160px_160px_auto]'>
      <div className='relative'>
        <Search className='absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400' />
        <Input
          value={value.keyword}
          onChange={(event) => update('keyword', event.target.value)}
          placeholder='搜索辩题或房间名'
          className='pl-9'
        />
      </div>
      <Select value={value.visibility} onValueChange={(next) => update('visibility', next as LobbyFilterValue['visibility'])}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value='all'>全部类型</SelectItem>
          <SelectItem value='public'>公开房间</SelectItem>
          <SelectItem value='private'>私密房间</SelectItem>
        </SelectContent>
      </Select>
      <Select value={value.status} onValueChange={(next) => update('status', next as LobbyFilterValue['status'])}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value='all'>全部状态</SelectItem>
          <SelectItem value='waiting'>候场中</SelectItem>
          <SelectItem value='full'>已满员</SelectItem>
          <SelectItem value='ongoing'>进行中</SelectItem>
        </SelectContent>
      </Select>
      <Select value={value.occupancy} onValueChange={(next) => update('occupancy', next as LobbyFilterValue['occupancy'])}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value='all'>全部人数</SelectItem>
          <SelectItem value='available'>尚有席位</SelectItem>
          <SelectItem value='almost_full'>接近满员</SelectItem>
        </SelectContent>
      </Select>
      <Select value={value.sort} onValueChange={(next) => update('sort', next as LobbySort)}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value='latest'>最新创建</SelectItem>
          <SelectItem value='hot'>人数最多</SelectItem>
          <SelectItem value='start_soon'>即将开始</SelectItem>
        </SelectContent>
      </Select>
      <Button variant='outline' onClick={onReset}>
        重置
      </Button>
    </div>
  );
};

export default DebateLobbyFilter;
