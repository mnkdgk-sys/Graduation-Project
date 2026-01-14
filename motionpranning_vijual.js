import React, { useState, useMemo } from 'react';
import { Play, Pause, SkipBack, Upload, Info } from 'lucide-react';

const MotionPlanVisualizer = () => {
  const [scoreData, setScoreData] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [selectedTrack, setSelectedTrack] = useState('both');

  // デモデータ
  const demoScoreData = {
    top: {
      bpm: 120,
      total_beats: 8,
      items: [
        { class: "note", beat: 0 },
        { class: "note", beat: 1 },
        { class: "note", beat: 2 },
        { class: "note", beat: 3 },
        { class: "note", beat: 4 },
        { class: "note", beat: 5 },
        { class: "note", beat: 6 },
        { class: "note", beat: 7 }
      ]
    },
    bottom: {
      bpm: 120,
      total_beats: 8,
      items: [
        { class: "note", beat: 0.5 },
        { class: "note", beat: 1.5 },
        { class: "note", beat: 2.5 },
        { class: "note", beat: 3.5 },
        { class: "note", beat: 4.5 },
        { class: "note", beat: 5.5 },
        { class: "note", beat: 6.5 },
        { class: "note", beat: 7.5 }
      ]
    }
  };

  // モーションプラン生成ロジック（元のコードから抽出）
  const generateMotionPlan = (noteItems, bpm, loopDuration) => {
    const MIN_EXPECTED_INTERVAL = 0.1;
    const MAX_EXPECTED_INTERVAL = 2.0;
    const MIN_VELOCITY = 100.0;
    const MAX_VELOCITY = 400.0;
    const MIN_ACCELERATION = 100.0;
    const MAX_ACCELERATION = 800.0;
    const MAX_BACKSWING_HEIGHT = 70;
    const MIN_BACKSWING_HEIGHT = 32;
    const EXPRESSION_EXPONENT = 0.75;
    const COMMUNICATION_LATENCY = 0.050;

    const notesOnly = noteItems
      .filter(item => item.class === "note")
      .sort((a, b) => a.beat - b.beat);

    if (notesOnly.length === 0) return [];

    const secondsPerBeat = 60.0 / bpm;
    const motionPlan = [];

    notesOnly.forEach((currentNote, i) => {
      const currentStrikeTime = currentNote.beat * secondsPerBeat;
      const nextNote = notesOnly[(i + 1) % notesOnly.length];
      const nextStrikeTime = nextNote.beat * secondsPerBeat;

      let interval;
      if (i === notesOnly.length - 1) {
        interval = (loopDuration - currentStrikeTime) + nextStrikeTime;
      } else {
        interval = nextStrikeTime - currentStrikeTime;
      }

      if (interval <= 0.02) return;

      const normalizedInterval = Math.max(0, Math.min(1,
        (interval - MIN_EXPECTED_INTERVAL) / (MAX_EXPECTED_INTERVAL - MIN_EXPECTED_INTERVAL)
      ));
      const easedRatio = Math.pow(normalizedInterval, EXPRESSION_EXPONENT);

      const backswingZ = MIN_BACKSWING_HEIGHT + (MAX_BACKSWING_HEIGHT - MIN_BACKSWING_HEIGHT) * easedRatio;
      const velocity = MIN_VELOCITY + (MAX_VELOCITY - MIN_VELOCITY) * (1.0 - easedRatio);
      const acceleration = MIN_ACCELERATION + (MAX_ACCELERATION - MIN_ACCELERATION) * (1.0 - easedRatio);

      // Strike motion
      motionPlan.push({
        targetTime: currentStrikeTime,
        action: "strike",
        position: { z: 22 },
        velocity: MAX_VELOCITY,
        acceleration: MAX_ACCELERATION,
        isCompensated: false,
        sendTime: currentStrikeTime - 0.1 - COMMUNICATION_LATENCY
      });

      // Upstroke motion
      const upstrokeStartTime = currentStrikeTime + 0.01;
      motionPlan.push({
        targetTime: upstrokeStartTime,
        action: "upstroke",
        position: { z: backswingZ },
        velocity: velocity,
        acceleration: acceleration,
        isCompensated: true,
        sendTime: upstrokeStartTime - COMMUNICATION_LATENCY
      });
    });

    return motionPlan.sort((a, b) => a.targetTime - b.targetTime);
  };

  const processedData = useMemo(() => {
    const data = scoreData || demoScoreData;
    
    const processTrack = (trackData, trackName) => {
      const bpm = trackData.bpm;
      const totalBeats = trackData.total_beats;
      const loopDuration = totalBeats * (60.0 / bpm);
      const secondsPerBeat = 60.0 / bpm;

      const notes = trackData.items
        .filter(item => item.class === "note")
        .map(note => ({
          beat: note.beat,
          time: note.beat * secondsPerBeat
        }));

      const motionPlan = generateMotionPlan(trackData.items, bpm, loopDuration);

      return { notes, motionPlan, loopDuration, bpm };
    };

    const top = data.top ? processTrack(data.top, 'top') : null;
    const bottom = data.bottom ? processTrack(data.bottom, 'bottom') : null;

    const maxDuration = Math.max(
      top?.loopDuration || 0,
      bottom?.loopDuration || 0
    );

    return { top, bottom, maxDuration };
  }, [scoreData]);

  // Playback control
  React.useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentTime(t => {
        const newTime = t + (0.016 * playbackSpeed);
        return newTime >= processedData.maxDuration ? 0 : newTime;
      });
    }, 16);

    return () => clearInterval(interval);
  }, [isPlaying, playbackSpeed, processedData.maxDuration]);

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const data = JSON.parse(event.target.result);
        setScoreData(data);
        setCurrentTime(0);
      } catch (err) {
        alert('JSONファイルの読み込みに失敗しました');
      }
    };
    reader.readAsText(file);
  };

  const renderTimeline = (trackData, trackName, color) => {
    if (!trackData) return null;

    const { notes, motionPlan, loopDuration } = trackData;
    const pixelsPerSecond = 800 / processedData.maxDuration;

    return (
      <div className="mb-8">
        <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${color}`}></div>
          {trackName === 'top' ? 'Top Track (Robot 1)' : 'Bottom Track (Robot 2)'}
        </h3>
        
        <div className="relative bg-gray-800 rounded-lg p-4 h-48">
          {/* Time grid */}
          <div className="absolute inset-0 flex">
            {Array.from({ length: Math.ceil(loopDuration) + 1 }, (_, i) => (
              <div
                key={i}
                className="border-l border-gray-700"
                style={{ left: `${(i / processedData.maxDuration) * 100}%` }}
              >
                <span className="text-xs text-gray-500 ml-1">{i}s</span>
              </div>
            ))}
          </div>

          {/* Notes */}
          <div className="absolute top-12 left-0 right-0 h-8">
            {notes.map((note, i) => (
              <div
                key={i}
                className={`absolute w-2 h-8 ${color} rounded-full opacity-60`}
                style={{ left: `${(note.time / processedData.maxDuration) * 100}%` }}
                title={`Note at beat ${note.beat.toFixed(2)} (${note.time.toFixed(3)}s)`}
              />
            ))}
            <div className="absolute left-0 top-1/2 text-xs text-gray-400">音符</div>
          </div>

          {/* Motion commands */}
          <div className="absolute top-24 left-0 right-0 h-20">
            {motionPlan.map((motion, i) => {
              const isStrike = motion.action === 'strike';
              const bgColor = isStrike ? 'bg-red-500' : 'bg-blue-500';
              const sendPos = (motion.sendTime / processedData.maxDuration) * 100;
              const targetPos = (motion.targetTime / processedData.maxDuration) * 100;

              return (
                <React.Fragment key={i}>
                  {/* Command send time */}
                  <div
                    className={`absolute w-1 h-4 ${bgColor} opacity-40`}
                    style={{ left: `${sendPos}%`, top: '0' }}
                    title={`Command send: ${motion.sendTime.toFixed(3)}s`}
                  />
                  {/* Arrow to target */}
                  <div
                    className={`absolute h-0.5 ${bgColor} opacity-30`}
                    style={{
                      left: `${sendPos}%`,
                      width: `${targetPos - sendPos}%`,
                      top: '10px'
                    }}
                  />
                  {/* Target time */}
                  <div
                    className={`absolute ${bgColor} rounded`}
                    style={{
                      left: `${targetPos}%`,
                      top: isStrike ? '20px' : '35px',
                      width: '3px',
                      height: isStrike ? '24px' : '16px'
                    }}
                    title={`${motion.action} at ${motion.targetTime.toFixed(3)}s\nZ: ${motion.position.z.toFixed(1)}mm\nV: ${motion.velocity.toFixed(0)} A: ${motion.acceleration.toFixed(0)}`}
                  />
                </React.Fragment>
              );
            })}
            <div className="absolute left-0 top-6 text-xs text-gray-400">Strike</div>
            <div className="absolute left-0 top-10 text-xs text-gray-400">Upstroke</div>
          </div>

          {/* Current time indicator */}
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-yellow-400"
            style={{ left: `${(currentTime / processedData.maxDuration) * 100}%` }}
          >
            <div className="absolute -top-1 -left-2 w-5 h-5 border-2 border-yellow-400 rounded-full bg-gray-900" />
          </div>
        </div>

        {/* Z-height visualization */}
        <div className="mt-4 bg-gray-800 rounded-lg p-4 h-32">
          <div className="text-sm text-gray-400 mb-2">Z軸高さ (mm)</div>
          <svg width="100%" height="80" className="overflow-visible">
            <defs>
              <linearGradient id={`grad-${trackName}`} x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor={color === 'bg-purple-500' ? '#a855f7' : '#3b82f6'} stopOpacity="0.3" />
                <stop offset="100%" stopColor={color === 'bg-purple-500' ? '#a855f7' : '#3b82f6'} stopOpacity="0.1" />
              </linearGradient>
            </defs>
            
            {/* Grid lines */}
            {[0, 20, 40, 60, 80].map(z => (
              <g key={z}>
                <line
                  x1="0"
                  y1={80 - z}
                  x2="100%"
                  y2={80 - z}
                  stroke="#374151"
                  strokeWidth="1"
                  strokeDasharray="2,2"
                />
                <text x="5" y={85 - z} fill="#9ca3af" fontSize="10">{z}</text>
              </g>
            ))}

            {/* Motion path */}
            <polyline
              points={motionPlan.map((m, i) => {
                const x = (m.targetTime / processedData.maxDuration) * 800;
                const y = 80 - m.position.z;
                return `${x},${y}`;
              }).join(' ')}
              fill="none"
              stroke={color === 'bg-purple-500' ? '#a855f7' : '#3b82f6'}
              strokeWidth="2"
            />
            
            {/* Fill area */}
            <polygon
              points={`0,80 ${motionPlan.map((m, i) => {
                const x = (m.targetTime / processedData.maxDuration) * 800;
                const y = 80 - m.position.z;
                return `${x},${y}`;
              }).join(' ')} 800,80`}
              fill={`url(#grad-${trackName})`}
            />
          </svg>
        </div>
      </div>
    );
  };

  return (
    <div className="w-full h-screen bg-gray-900 text-white p-6 overflow-auto">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold mb-2">🤖 ロボットモーションプラン可視化</h1>
          <p className="text-gray-400">音符のタイミングとロボットの動作コマンドを可視化</p>
        </div>

        {/* Controls */}
        <div className="bg-gray-800 rounded-lg p-4 mb-6 flex flex-wrap items-center gap-4">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg transition"
          >
            {isPlaying ? <Pause size={20} /> : <Play size={20} />}
            {isPlaying ? '一時停止' : '再生'}
          </button>

          <button
            onClick={() => setCurrentTime(0)}
            className="flex items-center gap-2 bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg transition"
          >
            <SkipBack size={20} />
            リセット
          </button>

          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-400">速度:</label>
            <select
              value={playbackSpeed}
              onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
              className="bg-gray-700 rounded px-3 py-2 text-sm"
            >
              <option value={0.25}>0.25x</option>
              <option value={0.5}>0.5x</option>
              <option value={1}>1x</option>
              <option value={2}>2x</option>
              <option value={4}>4x</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-400">表示:</label>
            <select
              value={selectedTrack}
              onChange={(e) => setSelectedTrack(e.target.value)}
              className="bg-gray-700 rounded px-3 py-2 text-sm"
            >
              <option value="both">両方</option>
              <option value="top">Top のみ</option>
              <option value="bottom">Bottom のみ</option>
            </select>
          </div>

          <label className="flex items-center gap-2 bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg cursor-pointer transition ml-auto">
            <Upload size={20} />
            <span>スコアJSON読込</span>
            <input
              type="file"
              accept=".json"
              onChange={handleFileUpload}
              className="hidden"
            />
          </label>
        </div>

        {/* Time display */}
        <div className="bg-gray-800 rounded-lg p-4 mb-6">
          <div className="text-center">
            <div className="text-4xl font-mono">
              {currentTime.toFixed(3)}s
            </div>
            <div className="text-sm text-gray-400 mt-1">
              / {processedData.maxDuration.toFixed(3)}s
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="bg-gray-800 rounded-lg p-4 mb-6">
          <div className="flex items-start gap-2 mb-2">
            <Info size={16} className="mt-0.5 flex-shrink-0" />
            <div className="text-sm text-gray-300">
              <div className="font-semibold mb-2">凡例:</div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                <div>• <span className="text-purple-400">紫の点</span>: 音符位置</div>
                <div>• <span className="text-red-400">赤の線</span>: Strike動作</div>
                <div>• <span className="text-blue-400">青の点</span>: 音符位置</div>
                <div>• <span className="text-blue-400">青の線</span>: Upstroke動作</div>
                <div>• <span className="text-yellow-400">黄色の線</span>: 現在時刻</div>
                <div>• 薄い色: コマンド送信時刻</div>
              </div>
            </div>
          </div>
        </div>

        {/* Timelines */}
        {(selectedTrack === 'both' || selectedTrack === 'top') && processedData.top &&
          renderTimeline(processedData.top, 'top', 'bg-purple-500')}
        
        {(selectedTrack === 'both' || selectedTrack === 'bottom') && processedData.bottom &&
          renderTimeline(processedData.bottom, 'bottom', 'bg-blue-500')}

        {/* Statistics */}
        <div className="bg-gray-800 rounded-lg p-4 mt-6">
          <h3 className="text-lg font-semibold mb-3">統計情報</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {processedData.top && (
              <div>
                <div className="text-purple-400 font-semibold">Top Track</div>
                <div className="text-gray-400">音符数: {processedData.top.notes.length}</div>
                <div className="text-gray-400">動作数: {processedData.top.motionPlan.length}</div>
                <div className="text-gray-400">BPM: {processedData.top.bpm}</div>
              </div>
            )}
            {processedData.bottom && (
              <div>
                <div className="text-blue-400 font-semibold">Bottom Track</div>
                <div className="text-gray-400">音符数: {processedData.bottom.notes.length}</div>
                <div className="text-gray-400">動作数: {processedData.bottom.motionPlan.length}</div>
                <div className="text-gray-400">BPM: {processedData.bottom.bpm}</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MotionPlanVisualizer;