current_status = "" # 当前状态
is_processing = False # 处理事件状态

def update_status(new_status: str):
    # 更新状态
    global current_status
    if new_status != current_status: # 检查状态是否更新
        print(new_status)
        current_status = new_status

def processing(status: bool = None):
    # 修改状态
    global is_processing
    if status is not None:  # 只有在传入参数时才修改状态
        is_processing = status
    return is_processing  # 返回当前状态