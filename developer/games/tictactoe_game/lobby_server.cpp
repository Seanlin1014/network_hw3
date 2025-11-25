#include <iostream>
#include <fstream>
#include <map>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <cstring>
#include <sstream>
using namespace std;

// ====== NEW: 資料模型，包含密碼、戰績、在線狀態 ======
struct Account {
    string pass;
    int win, lose, draw;
    bool online;

    // 🟢 預設建構子
    Account() : pass(""), win(0), lose(0), draw(0), online(false) {}

    // 🟢 自訂建構子（支援 Account{...} 初始化）
    Account(string p, int w, int l, int d, bool o)
        : pass(p), win(w), lose(l), draw(d), online(o) {}
};


map<string, Account> db;

// ====== NEW: 載入帳號（相容舊檔格式）======
// 支援兩種行：
// 1) user pass
// 2) user pass win lose draw
void load_db() {
    ifstream fin("account.txt");
    string line;
    while (getline(fin, line)) {
        if (line.empty()) continue;
        istringstream ss(line);
        string u, p; int w=0, l=0, d=0;
        ss >> u >> p;
        if (!ss.fail()) {
            if (!(ss >> w >> l >> d)) { w = l = d = 0; } // 舊檔只有帳密
            db[u] = Account{p, w, l, d, false};
        }
    }
}

// ====== NEW: 全量存檔（避免重覆附加）======
void save_db() {
    ofstream fout("account.txt", ios::trunc);
    for (auto &kv : db) {
        const string &u = kv.first;
        const Account &a = kv.second;
        fout << u << ' ' << a.pass << ' '
             << a.win << ' ' << a.lose << ' ' << a.draw << '\n';
    }
    fout.flush();
}

// ====== CHANGED: 單純新增帳號到 map 後呼叫 save_db() ======
void register_account(const string &user, const string &password) {
    db[user] = Account{password, 0, 0, 0, false};
    save_db();
}

void handle_client(int clientfd){
    char buff[1024];
    int n = read(clientfd, buff, sizeof(buff)-1);
    if (n <= 0) { close(clientfd); return; }
    buff[n] = '\0';

    string cmd, user, password, arg;
    stringstream ss(buff);
    ss >> cmd >> user >> password >> arg;

    string reply;

    if (cmd == "REGISTER") {
        if (db.count(user)) {
            reply = "USER_EXISTS";
        } else {
            register_account(user, password);     // CHANGED
            reply = "REGISTER_OK";
        }
    }
    else if (cmd == "LOGIN") {
        if (!db.count(user)) {
            reply = "LOGIN_FAIL UserNotFound";
        } else if (db[user].pass != password) {
            reply = "LOGIN_FAIL WrongPassword";
        } else if (db[user].online) {
            reply = "LOGIN_FAIL AlreadyOnline";
        } else {
            db[user].online = true;
            // NEW: 登入時把戰績帶回去（方便客戶端顯示）
            reply = "LOGIN_SUCCESS W=" + to_string(db[user].win) +
                    " L=" + to_string(db[user].lose) +
                    " D=" + to_string(db[user].draw);
        }
    }
    else if (cmd == "LOGOUT") { // NEW
        // 格式：LOGOUT <user>
        if (db.count(user)) {
            db[user].online = false;
            reply = "LOGOUT_OK";
            cout << "[Server] User " << user << " logged out." << endl;
        } else {
            reply = "LOGOUT_FAIL UserNotFound";
            cout << "[Server] Logout failed for " << user << " (not found)." << endl;
        }
    }
    else if (cmd == "REPORT") { // NEW: 回報一場對局結果並存檔
        // 格式：REPORT <user> WIN|LOSE|DRAW
        if (!db.count(user)) {
            reply = "REPORT_FAIL UserNotFound";
        } else {
            if (password == "WIN")       db[user].win++;
            else if (password == "LOSE") db[user].lose++;
            else if (password == "DRAW") db[user].draw++;
            else { reply = "REPORT_FAIL BadArg"; goto send; }
            save_db();
            reply = "REPORT_OK W=" + to_string(db[user].win) +
                    " L=" + to_string(db[user].lose) +
                    " D=" + to_string(db[user].draw);
        }
    }
    else if (cmd == "STATS") { // NEW: 查詢戰績（可選）
        // 格式：STATS <user>
        if (!db.count(user)) reply = "STATS_FAIL UserNotFound";
        else {
            reply = "STATS W=" + to_string(db[user].win) +
                    " L=" + to_string(db[user].lose) +
                    " D=" + to_string(db[user].draw);
        }
    }
    else {
        reply = "UNKNOWN_CMD";
    }

send:
    if (write(clientfd, reply.c_str(), reply.size()) < 0) {
        perror("write failed");
    }
    close(clientfd);
}

int main(){
    load_db();                                  // NEW
    int sockfd = socket(AF_INET, SOCK_STREAM, 0);
    int server_port = 15555;

    sockaddr_in serv{};
    serv.sin_family = AF_INET;
    serv.sin_addr.s_addr = INADDR_ANY;
    serv.sin_port = htons(server_port);
    if (bind(sockfd, (sockaddr*)&serv, sizeof(serv)) < 0) { perror("bind"); return 1; }
    if (listen(sockfd, 16) < 0) { perror("listen"); return 1; }

    cout << "[Lobby] listening on port " << server_port <<  "..." << endl;
    while (true) {
        sockaddr_in cli{};
        socklen_t len = sizeof(cli);
        int clientfd = accept(sockfd, (sockaddr*)&cli, &len);
        if (clientfd < 0) continue;

        char ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &cli.sin_addr, ip, sizeof(ip));
        int port = ntohs(cli.sin_port);

        cout << "[Lobby] ✅ Connection accepted from " << ip 
            << ":" << port << endl;

        handle_client(clientfd);
    }

    // 不會走到這裡，但保留語意
    for (auto &kv : db) kv.second.online = false;
}
