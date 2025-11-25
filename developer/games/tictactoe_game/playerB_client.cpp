#include <iostream>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>
#include <sstream>
#include <stdexcept>
#include <cstdio> // for snprintf
#include <netdb.h>   // for getaddrinfo()
#include <csignal>   // for signal()
#include <atomic>
using namespace std;

atomic<bool> running(true);  // 用來標記程式是否正在執行
string current_user = "";    // 登入時記下使用者名稱
int udpfd_global = -1;       // 全域保存 socket

const char* LOBBY_SERVER_IP = "127.0.0.1";
int LOBBY_PORT = 15555;
void send_logout_to_server(const std::string &user);


// 🔹 建立與 Lobby Server 的連線（支援主機名與 IP）

void handle_sigint(int sig) {
    cout << "\n\n[System] Caught Ctrl+C (SIGINT). Logging out...\n";
    if (!current_user.empty()) {
        send_logout_to_server(current_user);
        cout << "[System] User " << current_user << " logged out from Lobby.\n";
    }
    if (udpfd_global != -1) {
        close(udpfd_global);
        cout << "[System] UDP socket closed.\n";
    }
    running = false;
    exit(0);  // 正常結束程式
}

int connect_to_lobby() {
    struct addrinfo hints{}, *res = nullptr, *rp = nullptr;
    hints.ai_family = AF_INET;      // IPv4 only
    hints.ai_socktype = SOCK_STREAM;

    string port_str = to_string(LOBBY_PORT);
    int err = getaddrinfo(LOBBY_SERVER_IP, port_str.c_str(), &hints, &res);
    if (err != 0) return -1;

    int fd = -1;
    for (rp = res; rp != nullptr; rp = rp->ai_next) {
        fd = socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
        if (fd < 0) continue;
        if (connect(fd, rp->ai_addr, rp->ai_addrlen) == 0) break; // success
        close(fd);
        fd = -1;
    }
    freeaddrinfo(res);
    return fd;
}

// 🟢 統一封裝：傳送登出請求給伺服器 (TCP Port 15000)
void send_logout_to_server(const string &user) {
    int sockfd = connect_to_lobby();
    if (sockfd < 0) return;
    string msg = "LOGOUT " + user + "\n";
    send(sockfd, msg.c_str(), msg.size(), 0);

    char buf[128];
    int n = recv(sockfd, buf, sizeof(buf) - 1, 0);
    if (n > 0) {
        buf[n] = '\0';
        cout << "Server replied: " << buf << endl;
    }
    close(sockfd);
}

// -------------------------------
// 🟩 Lobby 通訊：TCP 登入/註冊/戰績回報
// -------------------------------
string talk_to_server_with_reply(const string &msg) {
    int sockfd = connect_to_lobby();
    if (sockfd < 0) return "ERR_CONNECT";

    string send_msg = msg + "\n";
    send(sockfd, send_msg.c_str(), send_msg.size(), 0);

    char buf[1024];
    int n = recv(sockfd, buf, sizeof(buf)-1, 0);
    if (n < 0) { close(sockfd); return "ERR_RECV"; }
    buf[n] = '\0';

    string reply(buf);
    close(sockfd);
    return reply;
}

// -------------------------------
// 🟩 遊戲邏輯：勝負判定
// -------------------------------
bool check_win(char board[3][3], char c) {
    for (int i = 0; i < 3; i++) {
        if (board[i][0]==c && board[i][1]==c && board[i][2]==c) return true;
        if (board[0][i]==c && board[1][i]==c && board[2][i]==c) return true;
    }
    if (board[0][0]==c && board[1][1]==c && board[2][2]==c) return true;
    if (board[0][2]==c && board[1][1]==c && board[2][0]==c) return true;
    return false;
}

// 🟩 遊戲邏輯：判斷棋盤是否已滿
bool is_full(char board[3][3]) {
    for (int i=0;i<3;i++)
        for (int j=0;j<3;j++)
            if (board[i][j]==' ') return false;
    return true;
}

// -------------------------------
// 🟩 美化棋盤
// -------------------------------
void printBoard(char b[3][3], const string& myName, const string& oppName, char myMark, char oppMark) {
#ifdef _WIN32
    (void)system("cls");
#else
    (void)system("clear");
#endif
    cout << "=========================================\n";
    cout << "         🎮 Tic-Tac-Toe Online 🎮\n";
    cout << "=========================================\n";
    cout << "You: " << myName << "  [" << myMark << "]"
         << "   vs   Opponent: " << oppName << "  [" << oppMark << "]\n";
    cout << "-----------------------------------------\n\n";
    cout << "    0   1   2\n";
    for (int i = 0; i < 3; i++) {
        cout << " " << i << " ";
        for (int j = 0; j < 3; j++) {
            cout << " " << b[i][j] << " ";
            if (j < 2) cout << "|";
        }
        cout << "\n";
        if (i < 2) cout << "   ---+---+---\n";
    }
    cout << "\n";
}

// -------------------------------
// 🟩 主程式
// -------------------------------
int main(int argc, char* argv[]) {
    string user, pass;
    if (argc > 1)
    LOBBY_SERVER_IP = argv[1];
    if (argc > 2)
        LOBBY_PORT = stoi(argv[2]);

    signal(SIGINT, handle_sigint);

    cout << "Using Lobby server " << LOBBY_SERVER_IP 
        << ":" << LOBBY_PORT << endl;
    int udpfd = -1;
    int bound_port = -1;

    // 🟢 登入重試系統
    while (true) {
        cout << "Enter username: ";
        cin >> user;
        cout << "Enter password: ";
        cin >> pass;

        string reg = "REGISTER " + user + " " + pass;
        string login = "LOGIN " + user + " " + pass;

        // 嘗試註冊
        talk_to_server_with_reply(reg);
        
        // 嘗試登入
        string login_reply = talk_to_server_with_reply(login);
        cout << "Server replied: " << login_reply << endl;

        if (login_reply.find("LOGIN_SUCCESS") != string::npos) {
            cout << "✅ Login successful!\n";
            break;
        } else if (login_reply.find("ERR_CONNECT") != string::npos) {
            cout << "❌ Cannot connect to lobby server. Program exit.\n";
            return 1;
        } else if (login_reply.find("AlreadyOnline") != string::npos) {
            cout << "⚠️ This account is already logged in. Try another user.\n";
        } else if (login_reply.find("WrongPassword") != string::npos) {
            cout << "❌ Wrong password. Please try again.\n";
        } else {
            cout << "Unknown reply, retrying login...\n";
        }
    }

    // 🟢 初始化 UDP socket (實作端口自動切換)
    udpfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (udpfd < 0) {
        perror("udp socket");
        send_logout_to_server(user);
        return 1;
    }

    current_user = user;
    udpfd_global = udpfd;

    sockaddr_in myaddr{};
    myaddr.sin_family = AF_INET;
    myaddr.sin_addr.s_addr = htonl(INADDR_ANY);
    
    int yes = 1;
    setsockopt(udpfd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));

    int start_port = 10001;
    const int MAX_PORT = 10100;   // 延伸可用範圍
    srand(time(nullptr));          // 讓每個 B 嘗試不同起始點
    start_port += rand() % 50;    // 10001~10050 之間隨機起點

    bool bound_ok = false;
    for (int attempt = 0; attempt < 100; ++attempt) {
        int try_port = start_port + (attempt % 100);  // 循環嘗試 10001~10100
        myaddr.sin_port = htons(try_port);

        if (bind(udpfd, (sockaddr*)&myaddr, sizeof(myaddr)) == 0) {
            bound_port = try_port;
            bound_ok = true;
            break;
        }
    }
    if (!bound_ok) {
        cerr << "[B] ❌ Failed to bind any UDP port between 10001 and 10100.\n";
        close(udpfd);
        send_logout_to_server(user);
        return 1;
    }
    cout << "[B] ✅ UDP server successfully bound to port " << bound_port << ". Waiting for invitation...\n";


    if (bound_port == -1) {
        cerr << "[B] ERROR: Failed to bind to any UDP port between 10001 and " << MAX_PORT << ".\n";
        close(udpfd);
        send_logout_to_server(user);
        return 1;
    }

    cout << "[B] UDP server successfully bound to port " << bound_port << ". Waiting for invitation...\n";

    // ---------------------------------------------------------
    // 🎯 最外層迴圈：等待邀請、遊戲流程 (實現持續匹配)
    // ---------------------------------------------------------
    char buff[1024];
    sockaddr_in peer{};
    socklen_t peerlen = sizeof(peer);

    while (true) {
        // --- 階段 1: UDP 監聽 ---
        int n = recvfrom(udpfd, buff, sizeof(buff)-1, 0, (sockaddr*)&peer, &peerlen);
        if (n < 0) { perror("recvfrom"); continue; }
        buff[n] = '\0';
        
        string opp_ip = inet_ntoa(peer.sin_addr);

        if (strcmp(buff, "DISCOVER") == 0) {
            // 收到 DISCOVER, 回覆 HERE <實際綁定埠號>
            char response[128];
            // ⭐️ 核心修正：將 bound_port 包含在回覆訊息中
            snprintf(response, sizeof(response), "HERE %d", bound_port);

            sendto(udpfd, response, strlen(response), 0, (sockaddr*)&peer, peerlen);
            cout << "[B] replied: " << response << " to " << opp_ip << ":" << ntohs(peer.sin_port) << "\n";
        }
        else if (strncmp(buff, "INVITE", 6) == 0) {
            cout << "[B] Received INVITE from " << opp_ip << ". Accept? (y/n): ";
            string resp; cin >> resp;
            if (resp == "y" || resp == "Y") {
                sendto(udpfd, "ACCEPT", 6, 0, (sockaddr*)&peer, peerlen);
                cout << "[B] Invitation accepted. Waiting for TCP PORT info...\n";
            } else {
                sendto(udpfd, "DECLINE", 7, 0, (sockaddr*)&peer, peerlen);
                cout << "[B] Invitation declined.\n";
            }
        }
        else if (strncmp(buff, "PORT ", 5) == 0) {
            buff[n] = '\0';
            int tcp_port = atoi(buff + 5);
            cout << "[B] Got TCP port from A: " << tcp_port << endl;

            // --- 建立 TCP 連線 ---
            int sockfd = socket(AF_INET, SOCK_STREAM, 0);
            if (sockfd < 0) {
                perror("tcp socket (B)");
                continue;
            }

            sockaddr_in aaddr{};
            aaddr.sin_family = AF_INET;
            aaddr.sin_port   = htons(tcp_port);
            aaddr.sin_addr   = peer.sin_addr;  // 使用 A 的來源 IP

            // 若連不到 → 通知 A 換 port
            if (connect(sockfd, (sockaddr*)&aaddr, sizeof(aaddr)) < 0) {
                perror("[B] connect failed");
                sendto(udpfd, "PORTFAIL", 8, 0, (sockaddr*)&peer, peerlen);
                close(sockfd);
                cout << "[B] Notify A to retry with another port.\n";
                continue; // 回主迴圈，等 A 發下一個 PORT
            }

            cout << "[B] Connected to A's TCP server on port " << tcp_port << "! Starting game...\n";

            // ↓↓↓ 這裡開始保留你原本「交換名稱、遊戲主迴圈」的程式碼，不要動 ↓↓↓
            // 交換名稱
            char opp_name[64];
            int nname = recv(sockfd, opp_name, sizeof(opp_name)-1, 0);
            string opp_name_str = "Opponent";
            if (nname > 0) { opp_name[nname] = '\0'; opp_name_str = opp_name; }
            send(sockfd, user.c_str(), user.size(), 0);

            // --- 階段 4: 遊戲主體 ---
            bool play_session_again = true;

            while (play_session_again) {
                char board[3][3] = {{' ',' ',' '},{' ',' ',' '},{' ',' ',' '}};
                printBoard(board, user, opp_name_str, 'O', 'X');
                
                bool game_finished = false;
                bool opponent_aborted = false;

                // 內層回合迴圈
                while (!game_finished) {
                    // 1. 玩家 A (X) 回合 (等待接收)
                    cout << "[B] Waiting for opponent's move (X)...\n";
                    char recvbuf[1024];
                    int n2 = recv(sockfd, recvbuf, sizeof(recvbuf), 0);
                    
                    if (n2 <= 0) {
                        cout << "[B] Opponent left the game/connection lost. Returning to lobby...\n";
                        opponent_aborted = true;
                        break;
                    }
                    if (strncmp(recvbuf, "QUIT", 4) == 0) {
                        cout << "[B] Opponent quit the game. Returning to lobby...\n";
                        opponent_aborted = true;
                        break;
                    }
                    
                    memcpy(board, recvbuf, sizeof(board)); // ✅ 正常更新棋盤

                    printBoard(board, user, opp_name_str, 'O', 'X');
                    if (check_win(board,'X')) {
                        cout << "😢 Player A wins!\n";
                        talk_to_server_with_reply("REPORT " + user + " LOSE");
                        game_finished = true;
                        break;
                    }
                    if (is_full(board)) {
                        cout << "🤝 Draw!\n";
                        talk_to_server_with_reply("REPORT " + user + " DRAW");
                        game_finished = true;
                        break;
                    }

                    // 2. 玩家 B (O) 回合
                    int row,col;
                    while (true) {
                        cout << "[B] Enter your move (row col) or 'q' to quit: ";
                        string input, input2;
                        cin >> input;

                        if (input=="q" || input=="Q") {
                            cout << "[B] You quit the game. Notifying opponent...\n";
                            const char *quitmsg = "QUIT";
                            send(sockfd, quitmsg, strlen(quitmsg), 0);
                            
                            // 執行登出並結束程式
                            send_logout_to_server(user);
                            close(sockfd);
                            close(udpfd);
                            cout << "[B] Bye 👋\n";
                            return 0; 
                        }

                        if (!(cin >> input2)) {
                            cout << "⚠️ Invalid input format! Please enter 'row col'.\n";
                            continue;
                        }

                        try { 
                            row = stoi(input); 
                            col = stoi(input2);
                        }
                        catch (...) { 
                            cout << "⚠️ Invalid input! Please enter numbers 0–2.\n"; continue; 
                        }
                        
                        if (row<0||row>2||col<0||col>2||board[row][col]!=' ') {
                            cout << "❌ Invalid move!\n"; continue;
                        }
                        break;
                    }
                    
                    board[row][col] = 'O';
                    printBoard(board, user, opp_name_str, 'O', 'X');
                    send(sockfd, board, sizeof(board), 0);

                    if (check_win(board,'O')) {
                        cout << "🏆 You win!\n";
                        talk_to_server_with_reply("REPORT " + user + " WIN");
                        game_finished = true;
                        break;
                    }
                    if (is_full(board)) {
                        cout << "🤝 Draw!\n";
                        talk_to_server_with_reply("REPORT " + user + " DRAW");
                        game_finished = true;
                        break;
                    }
                } // 內層遊戲回合迴圈結束

                // --- 遊戲結束後的處理 ---
                if (opponent_aborted) {
                    play_session_again = false; 
                    cout << "[B] Session aborted. Returning to lobby for rematch.\n";
                    break;
                }
                
                // 正常結束才詢問
                cout << "Play again? (y/n): ";
                char again; cin >> again;
                if (again=='n'||again=='N') {
                    cout << "[B] Session finished. Returning to lobby.\n";
                    play_session_again = false;
                }
            } // 遊戲會話迴圈結束 (Play again)

            // 🟢 清理 TCP 資源並返回匹配大廳
            close(sockfd);
            cout << "[B] TCP connection closed. Restarting matching process...\n";
            // Player B 保持登入狀態，直接回到外層 while(true) 等待下一個邀請
        }
        // 如果是 DISCOVER 或 DECLIINE，continue 會讓流程自然回到 while(true) 開頭
    }
    
    // 程式終止前的清理
    send_logout_to_server(user);
    close(udpfd);
    return 0;
}