module ov5640_capture (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK", X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF m_axis:control:status, ASSOCIATED_RESET resetn, FREQ_HZ 142857132" *)
    input wire clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST", X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input wire resetn,
    input wire [4:0] control,
    output wire [3:0] status,
    input wire cam_pclk,
    input wire cam_vsync,
    input wire cam_href,
    input wire [7:0] cam_data,
    output wire cam_scl,
    inout wire cam_sda,
    output wire cam_rst_n,
    output wire cam_pwdn,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TDATA" *)
    output wire [31:0] m_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TKEEP" *)
    output wire [3:0] m_axis_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TVALID" *)
    output wire m_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TREADY" *)
    input wire m_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TLAST" *)
    output wire m_axis_tlast
);
    assign cam_scl = control[0];
    assign cam_sda = control[1] ? 1'bz : 1'b0;
    assign cam_rst_n = control[2];
    assign cam_pwdn = control[3];

    (* ASYNC_REG = "TRUE" *) reg [1:0] arm_sync = 0;
    (* ASYNC_REG = "TRUE" *) reg [1:0] reset_sync = 0;
    always @(posedge cam_pclk) begin
        arm_sync <= {arm_sync[0], control[4]};
        reset_sync <= {reset_sync[0], resetn};
    end
    wire fifo_reset = !reset_sync[1] || !arm_sync[1];
    reg previous_vsync = 0, previous_href = 0;
    reg started = 0, done = 0, error = 0;
    reg [1:0] phase = 0;
    reg [7:0] high_byte = 0;
    reg [15:0] first_pixel = 0;
    reg [16:0] word_count = 0;
    reg [9:0] line_bytes = 0;
    reg [8:0] lines = 0;
    wire full, empty, wr_busy, rd_busy;
    wire [32:0] fifo_data;
    wire push = started && !done && !error && cam_href && phase == 3 && !full && !wr_busy;
    wire last_word = word_count == 86527;
    wire [32:0] packed_pixels = {last_word, high_byte, cam_data, first_pixel};

    always @(posedge cam_pclk) begin
        previous_vsync <= cam_vsync;
        previous_href <= cam_href;
        if (fifo_reset) begin
            started <= 0; done <= 0; error <= 0;
            phase <= 0; word_count <= 0; line_bytes <= 0; lines <= 0;
        end else begin
            if (cam_vsync && !previous_vsync) begin
                if (!started && !wr_busy) started <= 1;
                else if (started && !done) error <= 1;
            end
            if (started && !error) begin
                if (cam_href && !previous_href) line_bytes <= 1;
                else if (cam_href) line_bytes <= line_bytes + 1;
                if (!cam_href && previous_href) begin
                    if (line_bytes != 832 || phase != 0) error <= 1;
                    lines <= lines + 1;
                    if (lines == 415 && !done) error <= 1;
                end
                if (cam_href && !done) begin
                    phase <= phase + 1;
                    if (phase == 0 || phase == 2) high_byte <= cam_data;
                    if (phase == 1) first_pixel <= {high_byte, cam_data};
                    if (phase == 3) begin
                        if (full || wr_busy) error <= 1;
                        else begin
                            word_count <= word_count + 1;
                            if (last_word) done <= 1;
                        end
                    end
                end
            end
        end
    end

    xpm_fifo_async #(
        .FIFO_MEMORY_TYPE("block"), .FIFO_WRITE_DEPTH(2048),
        .WRITE_DATA_WIDTH(33), .READ_DATA_WIDTH(33),
        .READ_MODE("fwft"), .FIFO_READ_LATENCY(0),
        .CDC_SYNC_STAGES(2), .USE_ADV_FEATURES("0000"),
        .WR_DATA_COUNT_WIDTH(12), .RD_DATA_COUNT_WIDTH(12)
    ) frame_fifo (
        .rst(fifo_reset), .wr_clk(cam_pclk), .rd_clk(clk),
        .din(packed_pixels), .wr_en(push), .full(full), .wr_rst_busy(wr_busy),
        .dout(fifo_data), .rd_en(m_axis_tvalid && m_axis_tready),
        .empty(empty), .rd_rst_busy(rd_busy), .sleep(1'b0),
        .injectsbiterr(1'b0), .injectdbiterr(1'b0)
    );
    assign m_axis_tdata = fifo_data[31:0];
    assign m_axis_tlast = fifo_data[32];
    assign m_axis_tkeep = 4'b1111;
    assign m_axis_tvalid = !empty && !rd_busy;

    (* ASYNC_REG = "TRUE" *) reg [1:0] error_sync = 0, done_sync = 0;
    always @(posedge clk) begin
        error_sync <= {error_sync[0], error};
        done_sync <= {done_sync[0], done};
    end
    assign status = {!rd_busy, done_sync[1], error_sync[1], cam_sda};
endmodule
