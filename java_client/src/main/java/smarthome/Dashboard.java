package smarthome;

import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.SwingUtilities;
import javax.swing.SwingWorker;
import javax.swing.Timer;
import java.awt.BorderLayout;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.GridLayout;

/**
 * Dashboard desktop Java (Swing) — controla a mesma API do simulador web.
 * Execute com o servidor Python rodando em http://127.0.0.1:8000
 */
public class Dashboard extends JFrame {
    private final ApiClient api = new ApiClient("http://127.0.0.1:8000");
    private final JLabel statusLabel = new JLabel("Conectando…");
    private final JTextArea logArea = new JTextArea(12, 48);

    public Dashboard() {
        super("SmartHome IoT — Java Dashboard");
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setSize(720, 520);
        setLocationRelativeTo(null);

        logArea.setEditable(false);
        logArea.setFont(new Font(Font.MONOSPACED, Font.PLAIN, 12));

        JPanel top = new JPanel(new BorderLayout());
        top.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));
        top.add(statusLabel, BorderLayout.CENTER);

        JPanel buttons = new JPanel(new GridLayout(0, 3, 8, 8));
        buttons.setBorder(BorderFactory.createEmptyBorder(8, 10, 8, 10));
        addBtn(buttons, "LED ON", () -> api.postJson("/api/led", "{\"on\":true}"));
        addBtn(buttons, "LED OFF", () -> api.postJson("/api/led", "{\"on\":false}"));
        addBtn(buttons, "Buzzer", () -> api.postJson("/api/buzzer", "{\"on\":true}"));
        addBtn(buttons, "Abrir Porta", () -> api.postJson("/api/door", "{\"door_id\":\"main\",\"open\":true}"));
        addBtn(buttons, "Fechar Porta", () -> api.postJson("/api/door", "{\"door_id\":\"main\",\"open\":false}"));
        addBtn(buttons, "Garagem", () -> api.postJson("/api/door", "{\"door_id\":\"garage\",\"open\":true}"));
        addBtn(buttons, "Relé Sala", () -> api.postJson("/api/relay", "{\"channel\":\"1\",\"on\":true}"));
        addBtn(buttons, "Cenário Welcome", () -> api.postJson("/api/simulate", "{\"scenario\":\"welcome\"}"));
        addBtn(buttons, "Teste Sync", () -> api.postJson("/api/simulate", "{\"scenario\":\"sync_test\"}"));
        addBtn(buttons, "Atualizar", () -> api.get("/api/status"));
        addBtn(buttons, "Modo Noite", () -> api.postJson("/api/simulate", "{\"scenario\":\"night\"}"));
        addBtn(buttons, "Alarme", () -> api.postJson("/api/simulate", "{\"scenario\":\"alarm\"}"));

        JPanel south = new JPanel(new FlowLayout(FlowLayout.LEFT));
        south.add(new JLabel("Logs / Status bruto:"));

        add(top, BorderLayout.NORTH);
        add(buttons, BorderLayout.CENTER);
        add(new JScrollPane(logArea), BorderLayout.SOUTH);

        Timer timer = new Timer(2000, e -> refreshStatus());
        timer.start();
        refreshStatus();
    }

    private void addBtn(JPanel panel, String title, ThrowingRunnable action) {
        JButton btn = new JButton(title);
        btn.addActionListener(e -> runAsync(title, action));
        panel.add(btn);
    }

    private void runAsync(String title, ThrowingRunnable action) {
        new SwingWorker<String, Void>() {
            @Override
            protected String doInBackground() throws Exception {
                return action.run();
            }

            @Override
            protected void done() {
                try {
                    append(title + " → OK\n" + get());
                    refreshStatus();
                } catch (Exception ex) {
                    append(title + " → ERRO: " + ex.getMessage());
                }
            }
        }.execute();
    }

    private void refreshStatus() {
        new SwingWorker<String, Void>() {
            @Override
            protected String doInBackground() throws Exception {
                return api.get("/api/status");
            }

            @Override
            protected void done() {
                try {
                    String body = get();
                    statusLabel.setText("API online — veja detalhes no painel inferior");
                    if (logArea.getText().length() < 20) {
                        append(body);
                    }
                } catch (Exception ex) {
                    statusLabel.setText("API offline: " + ex.getMessage());
                }
            }
        }.execute();
    }

    private void append(String text) {
        logArea.append(text + "\n\n");
        logArea.setCaretPosition(logArea.getDocument().getLength());
    }

    @FunctionalInterface
    interface ThrowingRunnable {
        String run() throws Exception;
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> new Dashboard().setVisible(true));
    }
}
