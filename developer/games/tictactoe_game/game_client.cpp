#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>
#include <iostream>
#include <vector>
#include <sstream> 
#include <stdexcept> 
#include <algorithm>
#include <thread>    
#include <cmath>     
#include <netdb.h>   // for getaddrinfo
#include <csignal>   // for signal()
#include <atomic>
using namespace std;

atomic<bool> running(true);  // 用來標記程式是否正在執行
string current_user = "";    // 登入時記下使用者名稱
int udpfd_global = -1;       // 全域保存 socket

const char* LOBBY_SERVER_IP = "127.0.0.1";
int LOBBY_PORT = 15555; // 預設埠號，可被 argv[2] 覆寫

// 回傳已連線的 TCP socket，失敗回 -1
void send_logout_to_server(const std::string &user);

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
    hints.ai_family = AF_INET;      // 只用 IPv4
    hints.ai_socktype = SOCK_STREAM;

    string port_str = to_string(LOBBY_PORT);
    int err = getaddrinfo(LOBBY_SERVER_IP, port_str.c_str(), &hints, &res);
    if (err != 0) return -1;

    int fd = -1;
    for (rp = res; rp != nullptr; rp = rp->ai_next) {
        fd = socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
        if (fd < 0) continue;
        if (connect(fd, rp->ai_addr, rp->ai_addrlen) == 0) break;  // 成功
        close(fd);
        fd = -1;
    }
    freeaddrinfo(res);
    return fd;
}

string talk_to_server_with_reply(const string &msg) {
    int sockfd = connect_to_lobby();
    if (sockfd < 0) return "ERR_CONNECT";

    send(sockfd, msg.c_str(), msg.size(), 0);
    send(sockfd, "\n", 1, 0);  // 送一個換行避免伺服器 read() 卡住

    char buf[1024];
    int n = recv(sockfd, buf, sizeof(buf) - 1, 0);
    if (n < 0) { close(sockfd); return "ERR_RECV"; }
    buf[n] = '\0';
    string reply(buf);
    close(sockfd);

    reply.erase(remove_if(reply.begin(), reply.end(), ::isspace), reply.end());
    return reply;
}

void send_logout_to_server(const string &user) {
    int sockfd = connect_to_lobby();
    if (sockfd < 0) return;
    string msg = "LOGOUT " + user + "\n";
    send(sockfd, msg.c_str(), msg.size(), 0);
    char buf[64];
    recv(sockfd, buf, sizeof(buf)-1, 0);
    close(sockfd);
}

//輔助：印出棋盤

void printBoard(char b[3][3], const string& myName, const string& oppName, char myMark, char oppMark) {
#ifdef _WIN32
    (void)system("cls");
#else
    (void)system("clear");
#endif
    cout << "=========================================\n";
    cout << "          🎮 Tic-Tac-Toe Online 🎮\n";
    cout << "=========================================\n";
    cout << "You: " << myName << "  [" << myMark << "]"
         << "  vs  Opponent: " << oppName << "  [" << oppMark << "]\n";
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


// 檢查勝負和平局

bool check_win(char board[3][3], char c) {
    for (int i = 0; i < 3; i++) {
        if (board[i][0]==c && board[i][1]==c && board[i][2]==c) return true;
        if (board[0][i]==c && board[1][i]==c && board[2][i]==c) return true;
    }
    if (board[0][0]==c && board[1][1]==c && board[2][2]==c) return true;
    if (board[0][2]==c && board[1][1]==c && board[2][0]==c) return true;
    return false;
}

bool is_full(char board[3][3]) {
    for (int i=0;i<3;i++)
        for (int j=0;j<3;j++)
            if (board[i][j]==' ') return false;
    return true;
}


int main(int argc, char* argv[]) {
    string user, pass;
    if (argc > 1) {
    LOBBY_SERVER_IP = argv[1];
    }
    if (argc > 2) {
        LOBBY_PORT = stoi(argv[2]);
    }
    signal(SIGINT, handle_sigint);

    cout << "Using Lobby server " << LOBBY_SERVER_IP << ":" << LOBBY_PORT << endl;


    // 登入環節 (TCP 15000)
    while (true) {
        cout << "Enter username: ";
        cin >> user;
        cout << "Enter password: ";
        cin >> pass;

        string reg = "REGISTER " + user + " " + pass;
        string login = "LOGIN " + user + " " + pass;

        // 註冊
        talk_to_server_with_reply(reg);
        

        // 登入
        string login_reply = talk_to_server_with_reply(login);
        cout << "Server replied: " << login_reply << endl;

        if (login_reply.find("LOGIN_SUCCESS") != string::npos) {
            cout << "✅ Login successful!\n";
            size_t w = login_reply.find("W=");
            if (w != string::npos) {
                cout << "📊 Your record: " << login_reply.substr(w) << "\n";
            }
            break; 
        } else if (login_reply.find("ERR_CONNECT") != string::npos) {
            cout << "❌ Cannot connect to lobby server.\n";
            return 1; 
        } else {
             cout << "Login failed. Please try again.\n";
        }
    }

    // 初始化 UDP socket (用於掃描和邀請)
    int udpfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (udpfd < 0) {
        perror("udp socket");
        send_logout_to_server(user);
        return 1;
    }

    current_user = user;
    udpfd_global = udpfd;

    // 設定 UDP 超時，避免 scan 卡住
    struct timeval tv;
    tv.tv_sec = 2; // 2 秒超時
    tv.tv_usec = 0;
    setsockopt(udpfd, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);

    // CSIT 伺服器列表
    vector<string> servers = {
        "linux1.cs.nycu.edu.tw", "linux2.cs.nycu.edu.tw", "linux3.cs.nycu.edu.tw", 
        "linux4.cs.nycu.edu.tw", "127.0.0.1"
    };

    char buff[1024];
    sockaddr_in baddr{};

    // 最外層持續匹配迴圈
    while (true) {
        int connfd = -1; 
        int tcpfd = -1;  

        //掃描與邀請選擇 (UDP)
        while (true) {
            cout << "\n-----------------------------------------\n";
            cout << "Enter command (scan / exit / stats): ";
            string cmd;
            cin >> cmd;
            
            if (cmd == "exit") {
                send_logout_to_server(user);
                close(udpfd);
                return 0; 
            }
            
            if (cmd == "stats") {
                string stats = talk_to_server_with_reply("STATS " + user);
                if (stats.find("STATS") != string::npos) {
                    cout << "📊 " << stats << endl;
                }
                continue;
            }

            if (cmd == "scan") {
                // <IP, Port>
                vector<pair<string,int>> found_Bs;
                int start_port = 10000, end_port = 10100;

                cout << "[A] Scanning ports " << start_port << "–" << end_port << "...\n";

                // 發送 DISCOVER 廣播
                for (auto &server : servers) {
                    // --- 新增：先解析主機名 ---
                    in_addr resolved{};
                    if (inet_pton(AF_INET, server.c_str(), &resolved) != 1) {
                        addrinfo hints{}, *res = nullptr;
                        hints.ai_family = AF_INET;
                        hints.ai_socktype = SOCK_DGRAM;
                        if (getaddrinfo(server.c_str(), nullptr, &hints, &res) == 0) {
                            auto *sin = (sockaddr_in *)res->ai_addr;
                            resolved = sin->sin_addr;
                            freeaddrinfo(res);
                        } else {
                            cerr << "DNS lookup failed for " << server << endl;
                            continue;
                        }
                    }
                    // --------------------------

                    for (int port = start_port; port <= end_port; port++) {
                        sockaddr_in target{};
                        target.sin_family = AF_INET;
                        target.sin_addr = resolved;
                        target.sin_port = htons(port);
                        sendto(udpfd, "DISCOVER", 8, 0, (sockaddr *)&target, sizeof(target));
                    }
                }


                // 收集 HERE 回覆
                auto collect_replies = [&](int wait_sec){
                    // 使用前面設置的 socket 超時
                    this_thread::sleep_for(std::chrono::seconds(wait_sec));
                    
                    while (true) {
                        sockaddr_in from{};
                        socklen_t fromlen = sizeof(from);
                        // 使用 MSG_DONTWAIT 進行非阻塞接收，直到緩衝區清空或超時
                        int n = recvfrom(udpfd, buff, sizeof(buff)-1, MSG_DONTWAIT, (sockaddr*)&from, &fromlen);
                        if (n <= 0) break;
                        
                        buff[n] = '\0';
                        int port = ntohs(from.sin_port);
                        char ip[INET_ADDRSTRLEN];
                        inet_ntop(AF_INET, &(from.sin_addr), ip, INET_ADDRSTRLEN);

                        cout << "[A] Received HERE from " << ip << ":" << port << endl;

                        // 記錄 Player B 的資訊
                        found_Bs.push_back({ip, port});

                        // 修正：使用雙引號字串比較
                        if (strncmp(buff, "HERE", 4) == 0) {
                            int bport = 0;
                            sscanf(buff, "HERE %d", &bport);
                            char ip[INET_ADDRSTRLEN];
                            inet_ntop(AF_INET, &(from.sin_addr), ip, INET_ADDRSTRLEN);
                            found_Bs.push_back({ip, bport});
                            cout << "[A] HERE from " << ip << ":" << bport << endl;
                        }

                    }
                };

                collect_replies(3); // 等待 3 秒收集回覆
                
                // 去除重複的 Player B (同一 IP:Port 只算一次)
                std::sort(found_Bs.begin(), found_Bs.end());
                found_Bs.erase(std::unique(found_Bs.begin(), found_Bs.end()), found_Bs.end());

                if (found_Bs.empty()) {
                    cout << "[A] No Player B found.\n";
                    continue; 
                }

                cout << "\nAvailable Players:\n";
                for (size_t i = 0; i < found_Bs.size(); ++i) {
                    cout << "  [" << i << "] " << found_Bs[i].first << ":" << found_Bs[i].second << "\n";
                }

                int choice = -1;
                cout << "Choose a Player B to invite: ";
                string choice_str;
                
                // 處理 cin 緩衝區，確保下一次輸入乾淨
                if (!(cin >> choice_str)) {
                    cin.clear();
                    cin.ignore(numeric_limits<streamsize>::max(), '\n');
                    continue;
                }
                
                try {
                    choice = stoi(choice_str);
                } catch (...) { continue; }
                
                if (choice < 0 || choice >= (int)found_Bs.size()) { continue; }

                inet_pton(AF_INET, found_Bs[choice].first.c_str(), &baddr.sin_addr);
                baddr.sin_port = htons(found_Bs[choice].second);

                break; // 準備進入邀請流程
            }
        }
        
        // 階段 2: 傳送 INVITE (UDP) 並等待 ACCEPT/DECLINE
        const char *invite = "INVITE";
        baddr.sin_family = AF_INET;
        sendto(udpfd, invite, strlen(invite), 0, (sockaddr*)& baddr, sizeof(baddr));
        cout << "[A] sent INVITE, waiting for reply (20s timeout)...\n";

        char ansbuff[1024];
        sockaddr_in from2{};
        socklen_t from2len = sizeof(from2);
        
        // ⚠️ 重設 socket 超時為較長值 (例如 20 秒) 來等待回覆
        tv.tv_sec = 20; 
        tv.tv_usec = 0;
        setsockopt(udpfd, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);

        int n2 = recvfrom(udpfd, ansbuff, sizeof(ansbuff) - 1, 0, (sockaddr*)&from2, &from2len);
        
        // 恢復 socket 超時為短值
        tv.tv_sec = 2; 
        setsockopt(udpfd, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);
        
        if (n2 <= 0) {
            cout << "[A] Invitation timed out or failed. Returning to lobby.\n";
            continue; // 返回最外層迴圈重新掃描
        }
        
        ansbuff[n2] = '\0';
        cout << "[A] B replied: " << ansbuff << endl;

        // 處理拒絕或非預期回覆，返回掃描
        if (strncmp(ansbuff, "ACCEPT", 6) != 0) {
            cout << "[A] Invitation failed/declined. Returning to lobby.\n";
            continue; 
        }

        // 階段 3: 建立遊戲 TCP Server (用於連線遊戲)
        // 階段 3: 建立遊戲 TCP Server (用於連線遊戲)
        tcpfd = socket(AF_INET, SOCK_STREAM, 0);
        if (tcpfd < 0) { perror("tcp socket (A)"); continue; }

        sockaddr_in saddr{};
        saddr.sin_family = AF_INET;
        saddr.sin_addr.s_addr = INADDR_ANY;

        // ✅ 新增：自動尋找可用 port 並重試
        int game_port = 16000;
        const int MAX_PORT = 16100;
        bool bound = false;

        int yes = 1;
        setsockopt(tcpfd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));

        while (game_port <= MAX_PORT) {
            saddr.sin_port = htons(game_port);
            if (bind(tcpfd, (sockaddr*)&saddr, sizeof(saddr)) == 0) {
                bound = true;
                break;
            }
            game_port++;
        }

        if (!bound) {
            cerr << "[A] ❌ Failed to bind any port between 16000–16100. Returning to lobby.\n";
            close(tcpfd);
            continue;
        }

        if (listen(tcpfd, 1) < 0) {
            perror("listen (A)");
            close(tcpfd);
            continue;
        }

        // ✅ 通知對方這次使用的 port
        char portmsg[64];
        snprintf(portmsg, sizeof(portmsg), "PORT %d", game_port);
        sendto(udpfd, portmsg, strlen(portmsg), 0, (sockaddr*)&baddr, sizeof(baddr));
        cout << "[A] Sent TCP port info to B: " << portmsg << endl;

        // ✅ 等待對方確認是否能連線
        char confirm_buf[64];
        sockaddr_in confirm_from{};
        socklen_t confirm_len = sizeof(confirm_from);
        tv.tv_sec = 10; tv.tv_usec = 0;
        setsockopt(udpfd, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);

        int confirm_n = recvfrom(udpfd, confirm_buf, sizeof(confirm_buf)-1, 0,
                                (sockaddr*)&confirm_from, &confirm_len);

        if (confirm_n > 0) {
            confirm_buf[confirm_n] = '\0';
            if (strncmp(confirm_buf, "PORTFAIL", 8) == 0) {
                cout << "[A] ⚠️ B failed to connect to port " << game_port 
                    << ". Trying next port...\n";
                close(tcpfd);
                continue;  // 直接回去重試新的 port
            }
        }

        // ✅ 成功建立後進入 accept 階段
        cout << "[A] Waiting for B to connect on port " << game_port << "...\n";

        // 接受 Player B 連線 (需設定超時，避免無限等待)
        
        // ⚠️ 設定 TCP accept 超時 (使用 select)
        fd_set readfds;
        struct timeval tcp_tv;
        tcp_tv.tv_sec = 20; // 20秒等待 B 連線
        tcp_tv.tv_usec = 0;
        
        FD_ZERO(&readfds);
        FD_SET(tcpfd, &readfds);

        cout << "[A] TCP server listening, waiting for B to connect...\n";
        if (select(tcpfd + 1, &readfds, NULL, NULL, &tcp_tv) > 0) {
            connfd = accept(tcpfd, nullptr, nullptr); // 使用之前初始化的 connfd
            if (connfd < 0) { 
                perror("accept (A) failed after select"); close(tcpfd); continue; 
            }
        } else {
            cout << "[A] Timeout waiting for Player B to connect. Returning to lobby.\n";
            close(tcpfd); 
            continue;
        }

        cout << "[A] B connected! Game TCP session established.\n";

        // 交換玩家名稱
        send(connfd, user.c_str(), user.size(), 0);
        char opp_name[64];
        int nname = recv(connfd, opp_name, sizeof(opp_name)-1, 0);
        string opp_name_str = "Opponent";
        if (nname > 0) {
            opp_name[nname] = '\0';
            opp_name_str = opp_name;
            cout << "[A] Connected with opponent: " << opp_name_str << endl;
        }

        // 階段 4: 遊戲主體迴圈 (支援多局)
        bool play_session_again = true;
        // 🎯 NEW: 新增旗標，追蹤是否為玩家主動退出 (輸入 'q')
        bool quit_by_user = false; 

        while (play_session_again) {
            char board[3][3] = { {' ', ' ', ' '}, {' ', ' ', ' '}, {' ', ' ', ' '} };

            cout << "\n[A] Game start! You are X.\n";
            printBoard(board, user, opp_name_str, 'X', 'O');
            
            bool game_finished = false;
            
            // 遊戲回合迴圈
            while (!game_finished) {
                int row = -1, col = -1;

                // 玩家輸入回合
                while (true) {
                    cout << "Enter your move (row col) or 'q' to quit: ";
                    string line;

                    if (std::cin.peek() == '\n') {
                        std::cin.ignore(1, '\n');
                    }

                    if (!getline(cin, line)) {
                        cin.clear();
                        continue;
                    }

                    // 處理退出指令
                    if (!line.empty() && (line[0] == 'q' || line[0] == 'Q')) {
                        const char *quitmsg = "QUIT";
                        send(connfd, quitmsg, strlen(quitmsg), 0);
                        game_finished = true;
                        quit_by_user = true;
                        break;
                    }

                    // 解析輸入座標
                    stringstream ss(line);
                    if (!(ss >> row >> col)) {
                        cout << "Invalid format. Enter two numbers (row col).\n";
                        continue;
                    }

                    // 驗證座標合法性與是否已被佔用
                    if (row < 0 || row > 2 || col < 0 || col > 2 || board[row][col] != ' ') {
                        cout << "Invalid move. Try again.\n";
                        continue;
                    } else {
                        break;
                    }
                }

                if (game_finished) break;

                // 玩家 A 落子
                board[row][col] = 'X';
                printBoard(board, user, opp_name_str, 'X', 'O');
                if (send(connfd, board, sizeof(board), 0) <= 0) {
                    cout << "[A] Connection lost while sending move. Returning to lobby...\n";
                    play_session_again = false;
                    game_finished = true;
                    break;
                }

                // 判斷勝負或平手
                if (check_win(board, 'X')) {
                    cout << "[A] You win!\n";
                    talk_to_server_with_reply("REPORT " + user + " WIN");
                    game_finished = true;
                    continue;
                }

                if (is_full(board)) {
                    cout << "[A] Draw!\n";
                    talk_to_server_with_reply("REPORT " + user + " DRAW");
                    game_finished = true;
                    continue;
                }

                // 接收對手回合
                char recvbuf[1024];
                int n = recv(connfd, recvbuf, sizeof(recvbuf) - 1, 0);
                if (n <= 0) {
                    cout << "[A] Opponent left the game. Exiting...\n";
                    game_finished = true;
                    play_session_again = false;
                    continue;
                }

                recvbuf[n] = '\0';
                if (strncmp(recvbuf, "QUIT", 4) == 0) {
                    cout << "[A] Opponent quit the game. Exiting...\n";
                    game_finished = true;
                    continue;
                }

                // 更新棋盤
                memcpy(board, recvbuf, sizeof(board));
                printBoard(board, user, opp_name_str, 'X', 'O');

                // 判斷對手是否獲勝或平手
                if (check_win(board, 'O')) {
                    cout << "[A] Player B wins!\n";
                    talk_to_server_with_reply("REPORT " + user + " LOSE");
                    game_finished = true;
                    continue;
                }

                if (is_full(board)) {
                    cout << "[A] Draw!\n";
                    talk_to_server_with_reply("REPORT " + user + " DRAW");
                    game_finished = true;
                    continue;
                }
            }

            // 詢問是否再玩一局 (只有正常結束時才詢問)
            // 🎯 修正點 2: 只有在非主動退出 (且非連線中斷) 時才詢問
            if (game_finished && !std::cin.eof() && !quit_by_user) { 
                cout << "Play again? (y/n): ";
                char again;
                if (!(cin >> again)) {
                    // 處理 EOF 或錯誤輸入
                    again = 'n';
                }
                if (again == 'n' || again == 'N') {
                    play_session_again = false;
                    cout << "[A] Session finished. Returning to lobby.\n";
                }
            } else {
                // 主動退出 (quit_by_user == true) 或 非正常退出 (連線中斷)
                play_session_again = false;
                if (quit_by_user) {
                    cout << "[A] You quit the session. Returning to lobby for new match.\n";
                } else {
                    cout << "[A] Game session abruptly ended. Returning to lobby for new match.\n";
                }
            }
        } // 遊戲會話迴圈結束

        // 階段 5: 清理 TCP 資源 (安全關閉)
        if (connfd != -1) close(connfd); 
        if (tcpfd != -1) close(tcpfd); 

        cout << "[A] TCP resources closed. Restarting matching process...\n";

        // 返回最外層迴圈重新掃描
        continue;
    } // 最外層匹配迴圈結束

    // 程式終止前的登出
    cout << "[A] Unexpected exit. Logging out.\n";
    send_logout_to_server(user);
    close(udpfd);
    return 0;
}
    