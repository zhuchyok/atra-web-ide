import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowRight, Users, Layout, Zap, ShieldCheck, Database, GitBranch } from 'lucide-react';

const SwarmArchitecture = () => {
  return (
    <div className="p-6 bg-slate-50 min-h-screen font-sans">
      <div className="max-w-4xl mx-auto space-y-8">
        <header className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-slate-900">Singularity v28.6: Decentralized Island Swarm</h1>
          <p className="text-slate-500 text-lg">Архитектура самоорганизующейся мультиагентной системы</p>
        </header>

        {/* Workflow Diagram */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 relative">
          {/* Step 1 */}
          <Card className="border-blue-200 shadow-md relative z-10">
            <CardHeader className="pb-2">
              <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center mb-2">
                <Zap className="text-blue-600 w-6 h-6" />
              </div>
              <CardTitle className="text-sm uppercase text-blue-600 font-bold">1. Market Maker</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-slate-600">Оркестратор превращает запрос пользователя в <b>Goal</b> и публикует на Blackboard.</p>
            </CardContent>
          </Card>

          {/* Step 2 */}
          <Card className="border-purple-200 shadow-md relative z-10">
            <CardHeader className="pb-2">
              <div className="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center mb-2">
                <Layout className="text-purple-600 w-6 h-6" />
              </div>
              <CardTitle className="text-sm uppercase text-purple-600 font-bold">2. Blackboard (Redis)</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-slate-600">Глобальная биржа задач. Хранит цели, улики и статусы в реальном времени.</p>
              <div className="mt-2 flex flex-wrap gap-1">
                <Badge variant="secondary" className="text-[10px]">Atomic Lock</Badge>
                <Badge variant="secondary" className="text-[10px]">TTL Control</Badge>
              </div>
            </CardContent>
          </Card>

          {/* Step 3 */}
          <Card className="border-green-200 shadow-md relative z-10">
            <CardHeader className="pb-2">
              <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center mb-2">
                <Users className="text-green-600 w-6 h-6" />
              </div>
              <CardTitle className="text-sm uppercase text-green-600 font-bold">3. Autonomous Experts</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-slate-600">Воркеры сканируют доску и сами <b>забирают (Claim)</b> подходящие задачи.</p>
            </CardContent>
          </Card>
        </div>

        {/* Deep Dive Section */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-slate-800 flex items-center gap-2">
            <ShieldCheck className="text-emerald-500" /> Ключевые механизмы
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm">
              <h3 className="font-bold text-slate-700 mb-2 flex items-center gap-2">
                <Database className="w-4 h-4 text-blue-500" /> Атомарный Аукцион
              </h3>
              <p className="text-sm text-slate-500 leading-relaxed">
                Используется алгоритм <code>SET NX</code> в Redis. Это гарантирует, что даже если 10 экспертов увидят задачу одновременно, её получит только один. Race condition исключен на уровне ядра.
              </p>
            </div>
            <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm">
              <h3 className="font-bold text-slate-700 mb-2 flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-purple-500" /> Горизонтальный Swarm
              </h3>
              <p className="text-sm text-slate-500 leading-relaxed">
                Если задача помечена <code>#complex</code>, воркер не просто выполняет её, а разворачивает локальный "остров" (Island Model) для коллективного брейншторма.
              </p>
            </div>
          </div>
        </div>

        {/* Status Section */}
        <div className="p-4 bg-slate-900 text-white rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Database className="text-blue-400" />
            <div>
              <p className="text-xs text-slate-400 uppercase font-bold tracking-wider">Текущий статус</p>
              <p className="text-lg font-medium">Decentralization Level: 88%</p>
            </div>
          </div>
          <div className="text-right">
            <Badge className="bg-blue-500">Singularity v28.6 Active</Badge>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SwarmArchitecture;
