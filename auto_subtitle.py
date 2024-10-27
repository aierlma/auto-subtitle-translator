import os
import sys
import subprocess
import time
import shutil
import json5

def load_whisper_config():
    """加载Whisper配置文件"""
    config_path = os.path.join("faster-whisper-webui", "config.json5")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json5.loads(f.read())
    return config

def convert_to_wav(input_file):
    """将视频文件转换为WAV格式"""
    print("正在将视频转换为音频...")
    wav_path = input_file + '.wav'
    
    # 使用ffmpeg进行转换，保留前20秒
    cmd = [
        'ffmpeg.exe',
        '-y',              # 覆盖已存在的文件
        '-i', input_file,  # 输入文件
        '-acodec', 'pcm_s16le',  # 音频编码
        '-ac', '1',        # 单声道
        '-ar', '16000',    # 采样率
        '-t', '20',        # 保留前20秒
        wav_path
    ]
    
    process = subprocess.Popen(cmd)
    process.wait()
    print("音频转换完成")
    return wav_path

def run_whisper(input_file):
    """使用faster-whisper-webui生成字幕"""
    print("正在生成字幕...")
    config = load_whisper_config()
    output_dir = os.path.join(os.getcwd(), "faster-whisper-webui", config.get("output_dir", "output").strip("./"))
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 检查是否需要转换为WAV
    file_ext = os.path.splitext(input_file)[1].lower()
    if file_ext in ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm']:
        input_file = convert_to_wav(input_file)
    
    # 构建基本命令
    whisper_dir = os.path.join(os.getcwd(), "faster-whisper-webui")
    cmd = [
        "python",
        os.path.join(whisper_dir, "cli.py"),
        "--model", config.get("default_model_name", "large-v3"),
        "--whisper_implementation", config.get("whisper_implementation", "faster-whisper"),
        "--vad", config.get("default_vad", "silero-vad"),
        "--task", config.get("task", "transcribe"),
        "--output_dir", output_dir,
        "--language", "Japanese"  # 强制设置为日语
    ]
    
    # 添加VAD相关参数
    if config.get("vad_merge_window") is not None:
        cmd.extend(["--vad_merge_window", str(config["vad_merge_window"])])
    
    if config.get("vad_max_merge_size") is not None:
        cmd.extend(["--vad_max_merge_size", str(config["vad_max_merge_size"])])
    
    if config.get("vad_padding") is not None:
        cmd.extend(["--vad_padding", str(config["vad_padding"])])
    
    if config.get("vad_prompt_window") is not None:
        cmd.extend(["--vad_prompt_window", str(config["vad_prompt_window"])])
    
    if config.get("vad_cpu_cores") is not None:
        cmd.extend(["--vad_cpu_cores", str(config["vad_cpu_cores"])])
    
    if config.get("vad_parallel_devices"):
        cmd.extend(["--vad_parallel_devices", config["vad_parallel_devices"]])
    
    if config.get("auto_parallel", True):
        cmd.extend(["--auto_parallel", "True"])
    
    # 添加其他性能相关参数
    if config.get("compute_type"):
        cmd.extend(["--compute_type", config["compute_type"]])
    
    if config.get("device"):
        cmd.extend(["--device", config["device"]])
    
    # 添加输入文件
    cmd.append(input_file)
    
    # 设置工作目录
    print("执行命令:", " ".join(cmd))
    subprocess.run(cmd, cwd=whisper_dir)
    print("字幕生成完成")
    
    # 获取生成的srt文件路径
    srt_filename = os.path.basename(input_file) + "-subs.srt"
    srt_path = os.path.join(output_dir, srt_filename)
    
    # 如果生成了临时WAV文件，删除它
    if input_file.endswith('.wav'):
        os.remove(input_file)
    
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"字幕文件未生成: {srt_path}")
    
    return srt_path

def start_sakura_service():
    """启动Sakura翻译服务"""
    print("启动Sakura翻译服务...")
    sakura_dir = os.path.join(os.getcwd(), "Sakura_Launcher_GUI")
    cmd = [
        "python",
        "main.py"
    ]
    
    # 在新进程中启动服务，使用正确的工作目录
    process = subprocess.Popen(cmd, cwd=sakura_dir)
    
    # 等待服务启动
    print("请在Sakura Launcher GUI中点击运行按钮启动服务")
    print("服务启动后按Enter继续...")
    input()
    
    return process

def translate_subtitles(srt_path, sakura_address=None):
    """使用GalTransl-for-ASMR翻译字幕"""
    print("开始翻译字幕...")
    galtransl_dir = os.path.join(os.getcwd(), "GalTransl-for-ASMR")
    
    cmd = [
        "python",
        "cli.py",
        srt_path
    ]
    
    if sakura_address:
        cmd.append(sakura_address)
    
    subprocess.run(cmd, cwd=galtransl_dir)
    
    # 翻译后的文件在project/cache目录下
    translated_path = os.path.join(galtransl_dir, "project", "cache", 
                                 os.path.splitext(os.path.basename(srt_path))[0] + ".zh.srt")
    return translated_path

def main():
    if len(sys.argv) < 2:
        print("使用方法: python auto_subtitle.py <视频文件路径> [sakura_address]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    sakura_address = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(input_file):
        print(f"错误: 文件 {input_file} 不存在")
        sys.exit(1)
    
    try:
        # 1. 生成字幕
        srt_path = run_whisper(input_file)
        print(f"字幕文件已生成: {srt_path}")
        
        # 2. 启动Sakura服务
        sakura_process = start_sakura_service()
        
        # 3. 翻译字幕
        translated_path = translate_subtitles(srt_path, sakura_address)
        
        print(f"\n处理完成!")
        print(f"翻译后的字幕文件保存在: {translated_path}")
        
    finally:
        # 清理进程
        if 'sakura_process' in locals():
            sakura_process.terminate()

if __name__ == "__main__":
    main()
