#!/bin/sh

# ~/.binディレクトリが存在しない場合は作成
if [ ! -d "$HOME/.bin" ]; then
    echo "Creating $HOME/.bin directory..."
    mkdir -p "$HOME/.bin"
fi

# jobq.pyを~/.bin/jobqにコピー
echo "Copying jobq.py to $HOME/.bin/jobq..."
cp jobq.py "$HOME/.bin/jobq"

# 実行可能にする
echo "Making $HOME/.bin/jobq executable..."
chmod +x "$HOME/.bin/jobq"

echo "Installation complete!"
echo "Make sure $HOME/.bin is in your PATH."
