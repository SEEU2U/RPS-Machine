import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import cv2
import mediapipe as mp
import numpy as np
import os
import time

max_num_hands = 2
gesture = {
    0: 'fist', 1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five',
    6: 'six', 7: 'rock', 8: 'spiderman', 9: 'yeah', 10: 'ok',
}
rps_gesture = {0: 'rock', 5: 'paper', 9: 'scissors'}

# MediaPipe 손 모델 초기화
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    max_num_hands=max_num_hands,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5)

# 제스쳐 인식 모델 초기화
base_path = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(base_path, 'data/gesture_train.csv')
file = np.genfromtxt(file_path, delimiter=',')
angle = file[:, :-1].astype(np.float32)
label = file[:, -1].astype(np.float32)
knn = cv2.ml.KNearest_create()
knn.train(angle, cv2.ml.ROW_SAMPLE, label)

# 전역 변수 초기화
leftHand_wins = 0
rightHand_wins = 0

# 이전에 승리한 시간을 기록
win_time = time.time()

# 승리 판정 제한 시간을 3초로 설정
win_limit_sec = 3
time_remaining = win_limit_sec

# 게임을 시작하는 함수
def start_game(root, canvas, webcam_label, start_button, description_button, exit_button):
    global leftHand_wins, rightHand_wins, win_time, time_remaining  # 전역 변수를 선언

    cap = cv2.VideoCapture(0)

    # 메인 윈도우를 여는 함수
    def open_main_window():
        global leftHand_wins, rightHand_wins  # 전역 변수를 선언
        leftHand_wins = 0  # 왼쪽 손 승리 횟수 초기화
        rightHand_wins = 0  # 오른쪽 손 승리 횟수 초기화
        cap.release()
        root.destroy()
        main()

    # 웹캠에서 프레임을 읽어오는 함수
    def show_frame():
        global leftHand_wins, rightHand_wins, win_time, time_remaining  # 전역 변수를 선언
        ret, img = cap.read()
        if not ret:
            return

        img = cv2.flip(img, 1)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        result = hands.process(img)

        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        if result.multi_hand_landmarks is not None:
            rps_result = []

            for res in result.multi_hand_landmarks:
                joint = np.zeros((21, 3))
                for j, lm in enumerate(res.landmark):
                    joint[j] = [lm.x, lm.y, lm.z]

                # 조인트의 각도 계산
                v1 = joint[[0, 1, 2, 3, 0, 5, 6, 7, 0, 9, 10, 11, 0, 13, 14, 15, 0, 17, 18, 19], :]  # 부모 조인트
                v2 = joint[[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], :]  # 자식 조인트
                v = v2 - v1  # [20,3]
                # Normalize v 정규화
                v = v / np.linalg.norm(v, axis=1)[:, np.newaxis]

                # 점의 각도계산
                angle = np.arccos(np.einsum('nt,nt->n',
                                             v[[0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17, 18], :],
                                             v[[1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15, 17, 18, 19], :]))  # [15,]

                angle = np.degrees(angle)  # radian을 degree로 변환시킴

                # 제스쳐 추론
                data = np.array([angle], dtype=np.float32)
                ret, results, neighbours, dist = knn.findNearest(data, 3)
                idx = int(results[0][0])

                # 제스쳐의 결과를 그림
                if idx in rps_gesture.keys():
                    org = (int(res.landmark[0].x * img.shape[1]), int(res.landmark[0].y * img.shape[0]))
                    cv2.putText(img, text=rps_gesture[idx].upper(), org=(org[0], org[1] + 20),
                                fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=1, color=(255, 255, 255), thickness=2)

                    rps_result.append({
                        'rps': rps_gesture[idx],
                        'org': org
                    })

                mp_drawing.draw_landmarks(img, res, mp_hands.HAND_CONNECTIONS)

                # 누가 이겼는지 확인
                if len(rps_result) >= 2:
                    winner = None
                    text = ''

                    if rps_result[0]['rps'] == 'rock':
                        if rps_result[1]['rps'] == 'rock': text = 'Tie'
                        elif rps_result[1]['rps'] == 'paper': text = 'Paper wins'; winner = 1
                        elif rps_result[1]['rps'] == 'scissors': text = 'Rock wins'; winner = 0
                    elif rps_result[0]['rps'] == 'paper':
                        if rps_result[1]['rps'] == 'rock': text = 'Paper wins'; winner = 0
                        elif rps_result[1]['rps'] == 'paper': text = 'Tie'
                        elif rps_result[1]['rps'] == 'scissors': text = 'Scissors wins'; winner = 1
                    elif rps_result[0]['rps'] == 'scissors':
                        if rps_result[1]['rps'] == 'rock': text = 'Rock wins'; winner = 1
                        elif rps_result[1]['rps'] == 'paper': text = 'Scissors wins'; winner = 0
                        elif rps_result[1]['rps'] == 'scissors': text = 'Tie'

                    if winner is not None:
                        current_time = time.time()
                        time_elapsed = current_time - win_time
                        if time_elapsed >= win_limit_sec:
                            cv2.putText(img, text='Winner', org=(img.shape[1] // 2 - 100, img.shape[0] // 2),
                                        fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=2, color=(0, 255, 0), thickness=3)

                            # 승리 제한 시간 이후 승리한 경우에 이긴 횟수 증가
                            if rps_result[winner]['org'][0] < img.shape[1] // 2:
                                leftHand_wins += 1
                                if leftHand_wins == 5:
                                    cv2.putText(img, text='Finish', org=(img.shape[1] // 2 - 100, img.shape[0] // 2 - 50),
                                                fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=2, color=(0, 0, 255), thickness=3)
                                    cv2.putText(img, text='Winner Left', org=(img.shape[1] // 2 - 100, img.shape[0] // 2 + 50),
                                                fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=2, color=(0, 255, 0), thickness=3)
                                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                                    img = Image.fromarray(img)
                                    imgtk = ImageTk.PhotoImage(image=img)
                                    webcam_label.imgtk = imgtk
                                    webcam_label.configure(image=imgtk)
                                    webcam_label.after(5000, open_main_window)
                                    return
                            else:
                                rightHand_wins += 1
                                if rightHand_wins == 5:
                                    cv2.putText(img, text='Finish', org=(img.shape[1] // 2 - 100, img.shape[0] // 2 - 50),
                                                fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=2, color=(0, 0, 255), thickness=3)
                                    cv2.putText(img, text='Winner Right', org=(img.shape[1] // 2 - 100, img.shape[0] // 2 + 50),
                                                fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=2, color=(0, 255, 0), thickness=3)
                                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                                    img = Image.fromarray(img)
                                    imgtk = ImageTk.PhotoImage(image=img)
                                    webcam_label.imgtk = imgtk
                                    webcam_label.configure(image=imgtk)
                                    webcam_label.after(5000, open_main_window)
                                    return
                            win_time = current_time
                            time_remaining = win_limit_sec  # 타이머 초기화
                        else:
                            time_remaining = max(0, win_limit_sec - int(time_elapsed))
                            cv2.putText(img, text=f'Time :  {time_remaining}', org=(img.shape[1] // 2 - 100, 50),
                                        fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=1, color=(255, 0, 0), thickness=2)

                    # 왼쪽 손의 이긴 횟수를 표시
                    cv2.putText(img, text=str(leftHand_wins), org=(50, img.shape[0] - 50), fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                                fontScale=2, color=(0, 255, 255), thickness=3)
                    # 오른쪽 손의 이긴 횟수를 표시
                    cv2.putText(img, text=str(rightHand_wins), org=(img.shape[1] - 100, img.shape[0] - 50),
                                fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=2, color=(0, 255, 255), thickness=3)

                    cv2.putText(img, text=text, org=(img.shape[1] // 2 - 100, img.shape[0] // 2), fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                                fontScale=2, color=(0, 0, 255), thickness=3)

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(img)
        imgtk = ImageTk.PhotoImage(image=img)
        webcam_label.imgtk = imgtk
        webcam_label.configure(image=imgtk)

        root.after(10, show_frame)

    # 메뉴 버튼을 표시하는 함수
    def show_menu_buttons():
        main_button.place_forget()  # 메인 버튼을 숨김
        continue_button.place(x=350, y=200, width=100, height=50)
        main_menu_button.place(x=350, y=270, width=100, height=50)
        exit_game_button.place(x=350, y=340, width=100, height=50)

    # 메뉴 버튼을 숨기는 함수
    def hide_menu_buttons():
        continue_button.place_forget()
        main_menu_button.place_forget()
        exit_game_button.place_forget()
        main_button.place(x=720, y=20)

    start_button.destroy()  # START 버튼을 제거
    description_button.destroy()  # DESCRIPTION 버튼을 제거
    exit_button.destroy()  # EXIT 버튼을 제거
    webcam_label.place(x=0, y=0, width=800, height=600)  # 웹캠 피드를 캔버스를 꽉 채우도록 배치
    root.after(10, show_frame)

    main_button = tk.Button(root, text="메뉴", font=("Arial", 18), command=show_menu_buttons)
    main_button.place(x=720, y=20)

    continue_button = tk.Button(root, text="계속", font=("Arial", 18), command=hide_menu_buttons)
    main_menu_button = tk.Button(root, text="메인으로", font=("Arial", 18), command=open_main_window)
    exit_game_button = tk.Button(root, text="게임 종료", font=("Arial", 18), command=root.quit)

# 게임 설명 화면을 표시하는 함수
def show_description(canvas, root):
    canvas.delete("all")  # 현재 캔버스에 그려진 모든 내용을 삭제

    # 배경 이미지 파일 로드
    base_path = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(base_path, "image/background_EX.jpg")
    background_image = Image.open(image_path)
    background_image = background_image.resize((800, 600), Image.LANCZOS)
    background_photo = ImageTk.PhotoImage(background_image)

    # 배경 이미지를 표시
    canvas.create_image(0, 0, image=background_photo, anchor="nw")
    canvas.image = background_photo  # 이미지 객체를 참조로 저장하여 가비지 컬렉션 방지

    # 메인 윈도우를 여는 함수
    def open_main_window():
        root.destroy()
        main()

    main_button = tk.Button(root, text="메뉴", font=("Arial", 18), command=open_main_window)
    main_button.place(x=720, y=20)

# 메인 함수: 애플리케이션의 메인 윈도우를 설정하고 실행
def main():
    root = tk.Tk()
    root.title("RPS Game - Rock Paper Scissors")
    root.geometry("800x600")

    # 현재 스크립트의 디렉토리를 기준으로 이미지 경로 설정
    base_path = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(base_path, "image/MAIN.jpg")

    # 배경 이미지 파일 로드
    background_image = Image.open(image_path)
    background_image = background_image.resize((800, 600), Image.LANCZOS)
    background_photo = ImageTk.PhotoImage(background_image)

    # 배경 이미지를 표시할 캔버스 생성
    canvas = tk.Canvas(root, width=800, height=600)
    canvas.pack(fill="both", expand=True)
    canvas.create_image(0, 0, image=background_photo, anchor="nw")

    # 웹캠 피드에 대한 레이블 생성
    webcam_label = tk.Label(root)

    start_button = tk.Button(root, text="게임 시작", font=("Arial", 18), command=lambda: start_game(root, canvas, webcam_label, start_button, description_button, exit_button))
    start_button_window = canvas.create_window(400, 300, window=start_button)

    description_button = tk.Button(root, text="게임 설명", font=("Arial", 18), command=lambda: show_description(canvas, root))
    description_button_window = canvas.create_window(400, 370, window=description_button)

    # 게임 종료 버튼 추가
    exit_button = tk.Button(root, text="게임 종료", font=("Arial", 18), command=root.quit)
    exit_button_window = canvas.create_window(400, 440, window=exit_button)

    root.mainloop()

if __name__ == "__main__":
    main()
