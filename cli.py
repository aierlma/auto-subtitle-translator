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
    
    # 使用ffmpeg进行转换
    cmd = [
        'ffmpeg.exe',
        '-y',              # 覆盖已存在的文件
        '-i', input_file,  # 输入文件
        '-acodec', 'pcm_s16le',  # 音频编码
        '-ac', '1',        # 单声道
        '-ar', '16000',    # 采样率
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
    
    # 构建基本命令，其余设置请在json5配置文件中指定
    whisper_dir = os.path.join(os.getcwd(), "faster-whisper-webui")
    cmd = [
        "python",
        os.path.join(whisper_dir, "cli.py")
    ] # Configuration options that will be used if they are not specified in the command line arguments.

    
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
    # sakura服务在上一层目录中即os.getcwd()的父目录中

    sakura_dir = os.path.join(os.getcwd(), "..", "Sakura_Launcher_GUI")
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
    """使用GalTransl翻译字幕"""
    print("开始翻译字幕...")
    galtransl_dir = os.path.join(os.getcwd())
    
    cmd = [
        "python",
        "GalTransl-cli.py",
        srt_path
    ]
    
    if sakura_address:
        cmd.append(sakura_address)
    
    subprocess.run(cmd, cwd=galtransl_dir)
    
    # 翻译后的文件在project/cache目录下
    translated_path = os.path.join(galtransl_dir, "project", "cache", 
                                 os.path.splitext(os.path.basename(srt_path))[0] + ".zh.srt")
    return translated_path

def delete_repeated_sequences(srt_path):
    """预处理字幕文件，删除重复序列"""
    print("预处理日文字幕...")
    
    
    # 检查文件是否存在
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"字幕文件不存在: {srt_path}")

    try:
        from delete_repeat import delete_repeat_main
        delete_repeat_main(srt_path)
        
        # 获取处理后的文件路径
        output_srt = srt_path.rsplit('.', 1)[0] + '-merged.srt'
        
        if not os.path.exists(output_srt):
            raise FileNotFoundError(f"处理后的文件不存在: {output_srt}")
            
        # 删除原始字幕文件
        # os.remove(srt_path)
        # 重命名新生成的字幕文件
        # os.rename(output_srt, srt_path)
        return output_srt
        
    except subprocess.CalledProcessError as e:
        print(f"预处理失败: {str(e)}")
        raise
    except Exception as e:
        print(f"预处理过程中出错: {str(e)}")
        raise

def main():
    if len(sys.argv) < 2:
        print("使用方法: python cli.py <视频文件路径> [sakura_address|claude|gpt-4o-mini|sakura]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    sakura_address = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(input_file):
        print(f"错误: 文件 {input_file} 不存在")
        sys.exit(1)
    
    try:
        # 1. 启动Sakura服务
        if sakura_address:
            print(f"使用Sakura地址: {sakura_address}")
        
        else:
            sakura_process = start_sakura_service()

        # 2. 生成字幕
        srt_path = run_whisper(input_file)
        print(f"字幕文件已生成: {srt_path}")
        
        # 2.5 预处理字幕
        srt_path = delete_repeated_sequences(srt_path)
        
        # 3. 翻译字幕
        translated_path = translate_subtitles(srt_path, sakura_address)
        
        print(f"\n处理完成!")
        print(f"翻译后的字幕文件保存在: {translated_path}")
        
    finally:
        # 清理进程
        if 'sakura_process' in locals() and sakura_address:
            sakura_process.terminate()


if __name__ == "__main__":
    main()
