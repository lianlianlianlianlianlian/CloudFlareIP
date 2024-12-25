import asyncio
import aiohttp
import subprocess
import time

# 配置区域：可以在这里修改
IP_FILE_PATH = './COLO/NRT.txt'  # IP地址列表文件路径
PING_COUNT = 1  # 每个IP进行ping测试的次数
HTTP_TIMEOUT = 2  # HTTP请求超时时间（秒）
OUTPUT_FILE_PATH = './Ping/NRT_RESULT.txt'  # 输出结果保存的文件路径
FINAL_OUTPUT_PATH = './Ping/NRT_BEST.txt'  # 最终排序的输出文件路径

# 读取IP列表
def read_ip_list(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines()]

# 异步Ping一个IP并记录ping时间
async def ping_ip(ip):
    start_time = time.time()
    process = await asyncio.create_subprocess_exec('ping', '-c', str(PING_COUNT), ip, stdout=asyncio.subprocess.PIPE)
    stdout, _ = await process.communicate()
    end_time = time.time()
    
    # 获取ping时间
    ping_time = None
    if process.returncode == 0:
        for line in stdout.decode().splitlines():
            if 'time=' in line:
                ping_time = float(line.split('time=')[1].split(' ms')[0])
                break
    
    return ip, ping_time, end_time - start_time

# 异步HTTP请求并记录访问时间
async def access_ip(ip):
    url = f'http://{ip}'
    start_time = time.time()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=HTTP_TIMEOUT) as response:
                end_time = time.time()
                response_time = end_time - start_time
                return ip, response_time
        except Exception as e:
            return ip, None

# 写入实时结果到文件
def write_results_to_file(results, file_path):
    with open(file_path, 'a') as file:  # 使用追加模式
        file.write(f"IP: {results['ip']}, Ping时间: {results['ping_time']} ms, 访问时间: {results['access_time']} s\n")

# 写入最终排序结果到文件
def write_sorted_results_to_file(results, file_path):
    with open(file_path, 'w') as file:
        file.write("IP 排序（最优秀的排在最上面）:\n")
        for result in results:
            file.write(f"IP: {result['ip']}, Ping时间: {result['ping_time']} ms, 访问时间: {result['access_time']} s\n")

# 主函数，执行ping和HTTP请求
async def main():
    ip_list = read_ip_list(IP_FILE_PATH)
    
    # 打开文件并写入标题（只写一次）
    with open(OUTPUT_FILE_PATH, 'w') as file:
        file.write("IP 排序（最优秀的排在最上面）:\n")
    
    # 存储所有结果的列表
    all_results = []

    for ip in ip_list:
        ping_time = None
        access_time = None

        # 执行 ping 和 http 请求
        ping_ip_result = await ping_ip(ip)
        access_ip_result = await access_ip(ip)

        # 提取结果
        ip, ping_time, _ = ping_ip_result
        ip_access, access_time = access_ip_result

        if ping_time is not None and access_time is not None:
            result = {
                'ip': ip,
                'ping_time': ping_time,
                'access_time': access_time
            }

            # 实时写入到文件
            write_results_to_file(result, OUTPUT_FILE_PATH)

            # 将结果加入到所有结果列表
            all_results.append(result)

            print(f"实时结果已写入: {ip}, Ping时间: {ping_time} ms, 访问时间: {access_time} s")

    # 最终排序并写入最终结果文件
    sorted_results = sorted(all_results, key=lambda x: (x['ping_time'], x['access_time']))
    write_sorted_results_to_file(sorted_results, FINAL_OUTPUT_PATH)

    print(f"所有结果已实时写入到 {OUTPUT_FILE_PATH}")
    print(f"最终排序结果已写入到 {FINAL_OUTPUT_PATH}")

if __name__ == '__main__':
    asyncio.run(main())
