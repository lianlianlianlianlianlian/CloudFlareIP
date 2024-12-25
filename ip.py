import random
import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress

# 从 ip.txt 中读取 IP 段
with open('ip.txt', 'r') as f:
    ip_ranges = [line.strip() for line in f if line.strip()]

# 生成所有 IP 地址
all_ips = []
for ip_range in ip_ranges:
    network = ipaddress.ip_network(ip_range, strict=False)
    all_ips.extend([str(ip) for ip in network.hosts()])  # 生成 IP，忽略网络和广播地址

# 随机选择 IP 地址（注意这次选择了全部 IP）
total_ips_to_select = min(1524400, len(all_ips))
print(f"随机选择的 IP 地址: {total_ips_to_select}")

selected_ips = random.sample(all_ips, total_ips_to_select)

# 分批处理，定义每批次大小
batch_size = 50000  # 每批处理 50000 个 IP
num_batches = (total_ips_to_select // batch_size) + 1

# 存储访问失败的 IP 地址和失败次数
failed_ips = []

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
    batch_ips = selected_ips[batch_num * batch_size:(batch_num + 1) * batch_size]
    print(f"处理第 {batch_num + 1} 批，共 {len(batch_ips)} 个 IP")

    colo_ip_cache = {}  # 用来缓存每批次的 IP

    # 增加 max_workers 到适当值以提高并发数
    with ThreadPoolExecutor(max_workers=100) as executor:  # 提高并发数以加速执行
        futures = {executor.submit(fetch_colo, ip): ip for ip in batch_ips}
        
        for future in as_completed(futures):
            ip = futures[future]
            colo_response = future.result()
            if colo_response:
                for line in colo_response.splitlines():
                    if line.startswith("colo="):
                        colo_value = line.split("=")[1]
                        # 缓存到内存中的 colo 值对应的 IP 列表
                        if colo_value not in colo_ip_cache:
                            colo_ip_cache[colo_value] = set()  # 使用 set 去重
                        colo_ip_cache[colo_value].add(ip)
                        # 实时写入文件（禁用缓冲区）
                        with open(f"{colo_value}.txt", 'a', buffering=1) as f:
                            f.write(f"{ip}\n")
                            f.flush()  # 手动刷新缓冲区，确保数据立即写入
            else:
                print(f"IP {ip} 访问失败，跳过。")

    # 批次处理结束时输出当前失败的 IP 列表
    if failed_ips:
        print(f"第 {batch_num + 1} 批处理后失败的 IP:")
        for fail_ip in failed_ips:
            print(fail_ip)
        # 清空 failed_ips 列表，为下一批次重用
        failed_ips = []

print("所有批次处理完成")
