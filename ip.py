import random
import requests
import os
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress

# 自定义目录和文件路径参数
output_directory = "./Colo"  # 自定义目录，存储机场的 IP 地址文件
progress_file = "progress.json"  # 进度文件路径

# 如果目录不存在，则创建目录
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

# 从 ip.txt 中读取 IP 段
with open('ip.txt', 'r') as f:
    ip_ranges = [line.strip() for line in f if line.strip()]

# 生成所有 IP 地址
all_ips = []
for ip_range in ip_ranges:
    network = ipaddress.ip_network(ip_range, strict=False)
    all_ips.extend([str(ip) for ip in network.hosts()])  # 生成 IP，忽略网络和广播地址

# 选择 IP 地址
total_ips_to_select = min(1524400, len(all_ips))
print(f"所有 IP 地址: {total_ips_to_select}")

selected_ips = random.sample(all_ips, total_ips_to_select)

# 分批处理，定义每批次大小
batch_size = 500  # 每批处理 500 个 IP
num_batches = (total_ips_to_select // batch_size) + 1

# 读取已处理的 IP 地址
def load_progress():
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {}

# 保存进度
def save_progress(progress_data):
    with open(progress_file, 'w') as f:
        json.dump(progress_data, f)

# 初始化进度数据
progress = load_progress()

# 使用字典记录每个 IP 的机场代码
ip_to_colo = progress.get("ip_to_colo", {})

# 从 IP 地址列表中去除已处理的 IP
remaining_ips = [ip for ip in selected_ips if ip not in ip_to_colo]

# 获取失败的 IP 地址
failed_ips = progress.get("failed_ips", [])

# 更新 IP 的机场代码
def update_ip_colo(ip, new_colo_value):
    # 先删除原来的机场代码记录
    old_colo_value = ip_to_colo.get(ip)
    if old_colo_value and old_colo_value != new_colo_value:
        # 从原机场代码文件中删除 IP
        with open(os.path.join(output_directory, f"{old_colo_value}.txt"), 'r') as f:
            lines = f.readlines()
        with open(os.path.join(output_directory, f"{old_colo_value}.txt"), 'w') as f:
            for line in lines:
                if line.strip() != ip:
                    f.write(line)
    
    # 更新 IP 的机场代码
    ip_to_colo[ip] = new_colo_value
    # 将新机场代码写入文件
    with open(os.path.join(output_directory, f"{new_colo_value}.txt"), 'a', buffering=1) as f:
        f.write(f"{ip}\n")
        f.flush()

# 请求 URL 获取 colo 信息
def fetch_colo(ip):
    url = f"http://{ip}/cdn-cgi/trace"
    try:
        response = requests.get(url, timeout=5)  # 设置5秒超时，避免长时间等待
        if response.status_code == 200:
            return response.text
    except requests.RequestException:
        failed_ips.append(ip)  # 访问失败直接记录
    return None

# 分批处理 IP 地址
for batch_num in range(num_batches):
    batch_ips = remaining_ips[batch_num * batch_size:(batch_num + 1) * batch_size]
    print(f"处理第 {batch_num + 1} 批，共 {len(batch_ips)} 个 IP")

    colo_ip_cache = {}  # 用来缓存每批次的 IP

    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(fetch_colo, ip): ip for ip in batch_ips}

        for future in as_completed(futures):
            ip = futures[future]
            colo_response = future.result()
            if colo_response:
                for line in colo_response.splitlines():
                    if line.startswith("colo="):
                        colo_value = line.split("=")[1]
                        # 更新 IP 的机场代码
                        update_ip_colo(ip, colo_value)
            else:
                print(f"IP {ip} 访问失败，跳过。")

    # 每次批次处理结束时保存进度
    progress["ip_to_colo"] = ip_to_colo
    progress["failed_ips"] = failed_ips  # 保存失败的 IP
    save_progress(progress)

    # 批次处理结束时输出当前失败的 IP 列表
    if failed_ips:
        print(f"第 {batch_num + 1} 批处理后失败的 IP:")
        for fail_ip in failed_ips:
            print(fail_ip)
        # 清空 failed_ips 列表，为下一批次重用
        failed_ips = []

print("所有批次处理完成")
