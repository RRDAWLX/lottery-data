"""Flask 服务入口，提供预测 REST API 和 SSE 事件推送。

启动后自动触发两个彩票模型的训练。训练状态通过观察者模式通知所有 SSE 订阅者。
观察者通过 observerId 去重：相同 id 替换旧队列，防止重复监听。
"""

import os
import sys
import json
import threading
import queue
import uuid

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request, Response

app = Flask(__name__)

# 各彩票类型的训练状态: idle / training / ready / error
training_status = {
    'unionLotto': 'idle',
    'superLotto': 'idle',
}

# 防止同一种彩票类型并发训练
training_lock = threading.Lock()

# 观察者字典，key 为 observerId，value 为 queue.Queue
# 相同 observerId 的新连接会替换旧队列，实现去重
observers = {}
observer_lock = threading.Lock()


def get_config():
    """读取项目根目录的 config.json，返回配置字典（含端口等设置）。"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def notify_observers(lottery_type, status, prediction=None):
    """训练状态变更时，向所有观察者推送 SSE 事件。"""
    event_data = {
        'lotteryType': lottery_type,
        'status': status,
    }
    if prediction is not None:
        event_data['prediction'] = prediction
    message = f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
    with observer_lock:
        # 推送失败（队列已满或关闭）的观察者直接移除
        dead = []
        for observer_id, q in observers.items():
            try:
                q.put_nowait(message)
            except Exception:
                dead.append(observer_id)
        for observer_id in dead:
            del observers[observer_id]


def train_in_background(lottery_type, force_full=False):
    """在后台线程中执行训练，训练完成后自动生成预测并通知观察者。"""
    from train import run_training, run_prediction

    with training_lock:
        if training_status[lottery_type] == 'training':
            return
        training_status[lottery_type] = 'training'

    notify_observers(lottery_type, 'training')

    try:
        model = run_training(lottery_type, force_full=force_full)
        if model is None:
            training_status[lottery_type] = 'error'
            notify_observers(lottery_type, 'error')
            return

        prediction = run_prediction(lottery_type)
        if prediction is not None:
            training_status[lottery_type] = 'ready'
            notify_observers(lottery_type, 'ready', prediction)
        else:
            training_status[lottery_type] = 'error'
            notify_observers(lottery_type, 'error')
    except Exception as e:
        print(f"[{lottery_type}] Training error: {e}")
        training_status[lottery_type] = 'error'
        notify_observers(lottery_type, 'error')


@app.route('/api/predict/<lottery_type>', methods=['GET'])
def predict(lottery_type):
    """获取预测结果。训练中返回 code=2，无模型返回 code=3。"""
    from train import run_prediction

    if lottery_type not in ('unionLotto', 'superLotto'):
        return jsonify({'code': 1, 'msg': 'invalid lottery type'}), 400

    status = training_status.get(lottery_type, 'idle')
    if status == 'training':
        return jsonify({'code': 2, 'msg': 'training in progress', 'data': {'status': 'training'}})

    prediction = run_prediction(lottery_type)
    if prediction is None:
        return jsonify({'code': 3, 'msg': 'model not available', 'data': {'status': status, 'prediction': None}})

    return jsonify({'code': 0, 'msg': 'success', 'data': {'status': 'ready', 'prediction': prediction}})


@app.route('/api/train/<lottery_type>', methods=['POST'])
def train(lottery_type):
    """触发异步训练。forceFull=true 时从零训练，否则增量训练。"""
    if lottery_type not in ('unionLotto', 'superLotto'):
        return jsonify({'code': 1, 'msg': 'invalid lottery type'}), 400

    force_full = request.args.get('forceFull', 'false').lower() == 'true'

    if training_status[lottery_type] == 'training':
        return jsonify({'code': 2, 'msg': 'already training'}), 409

    thread = threading.Thread(target=train_in_background, args=(lottery_type, force_full))
    thread.daemon = True
    thread.start()

    return jsonify({'code': 0, 'msg': 'training started'})


@app.route('/api/status/<lottery_type>', methods=['GET'])
def status(lottery_type):
    """查询当前训练状态，不需要预测结果时使用此接口。"""
    if lottery_type not in ('unionLotto', 'superLotto'):
        return jsonify({'code': 1, 'msg': 'invalid lottery type'}), 400

    status = training_status.get(lottery_type, 'idle')
    return jsonify({'code': 0, 'msg': 'success', 'data': {'status': status}})


@app.route('/api/events', methods=['GET'])
def events():
    """SSE 事件流端点。通过 observerId 参数去重，相同 id 替换旧观察者。

    事件格式: data: {"lotteryType":"unionLotto","status":"ready","prediction":[...]}
    """
    observer_id = request.args.get('observerId') or str(uuid.uuid4())
    q = queue.Queue()
    with observer_lock:
        # 相同 observerId 直接替换旧队列，防止重复监听
        observers[observer_id] = q

    def generate():
        try:
            while True:
                try:
                    message = q.get(timeout=30)
                    yield message
                except queue.Empty:
                    # 每 30s 发送心跳，防止连接被代理/负载均衡器超时断开
                    yield ': keepalive\n\n'
        except GeneratorExit:
            pass
        finally:
            with observer_lock:
                # 仅当队列未被新连接替换时才删除，避免误删新观察者
                if observer_id in observers and observers[observer_id] is q:
                    del observers[observer_id]

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'})


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查端点，用于判断服务是否正常运行。"""
    return jsonify({'code': 0, 'msg': 'ok'})


def init_on_startup():
    """启动时为两种彩票各启动一个训练线程。"""
    for lottery_type in ['unionLotto', 'superLotto']:
        thread = threading.Thread(target=train_in_background, args=(lottery_type, False))
        thread.daemon = True
        thread.start()


if __name__ == '__main__':
    config = get_config()
    port = config['prediction']['port']
    init_on_startup()
    app.run(host='0.0.0.0', port=port)