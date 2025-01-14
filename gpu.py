# import subprocess  

# def check_gpu():  
#     try:  
#         output = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv"])  
#         print(output.decode("utf-8"))  
#     except FileNotFoundError:  
#         print("nvidia-smi not found. GPU may not be available or NVIDIA drivers are not installed.")  



# import torch  

# def check_gpu1():
#     # 检查是否有可用的 GPU  
#     if torch.cuda.is_available():  
#         # 获取 GPU 数量  
#         gpu_count = torch.cuda.device_count()  
#         print(f"系统中有 {gpu_count} 个 GPU")  

#         # 打印每个 GPU 的信息  
#         for i in range(gpu_count):  
#             print(f"GPU {i}: {torch.cuda.get_device_name(i)}")  
#     else:  
#         print("系统中没有可用的 GPU")
# check_gpu()

# check_gpu1()



import subprocess  

def get_gpu_info():  
    try:  
        # 调用 nvidia-smi 命令获取 GPU 信息  
        output = subprocess.check_output(  
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv"]  
        ).decode("utf-8")  

        # 解析输出  
        gpu_info = []  
        lines = output.strip().split("\n")  # 按行分割  
        for i, line in enumerate(lines[1:]):  # 跳过第一行标题  
            name, driver_version, memory_total = line.split(", ")  
            gpu_info.append({  
                "id": i,  
                "name": name,  
                "driver_version": driver_version,  
                "memory_total": memory_total  
            })  
        return gpu_info  
    except Exception as e:  
        print(f"无法获取 GPU 信息: {e}")  
        return []  


def check_gpu():    
    # 获取并打印 GPU 信息  
    gpu_info = get_gpu_info()  
    if gpu_info:  
    print(f"系统中有 {len(gpu_info)} 个 GPU:")  
    for gpu in gpu_info:  
        print(f"GPU {gpu['id']}: {gpu['name']}, 驱动版本: {gpu['driver_version']}, 显存总量: {gpu['memory_total']}")  
    else:  
        print("系统中没有可用的 GPU 或无法获取 GPU 信息")