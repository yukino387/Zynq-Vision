`timescale 1ns/1ps
module capture_tb;
    reg clk = 0, pclk = 0, resetn = 0;
    always #5 clk = ~clk;
    always #20 pclk = ~pclk;
    reg [4:0] control = 7;
    reg vsync = 0, href = 0;
    reg [7:0] data = 0;
    wire [3:0] status;
    wire [31:0] output_data;
    wire valid, last;
    reg ready = 1;
    tri1 sda;
    ov5640_capture dut (.clk(clk), .resetn(resetn), .control(control), .status(status),
        .cam_pclk(pclk), .cam_vsync(vsync), .cam_href(href), .cam_data(data),
        .cam_sda(sda), .m_axis_tdata(output_data), .m_axis_tvalid(valid),
        .m_axis_tlast(last), .m_axis_tready(ready));
    integer received = 0, clocks = 0;
    reg [31:0] expected;
    always @(posedge clk) begin
        clocks <= clocks + 1;
        ready <= clocks % 17 > 3;
        if (valid && ready) begin
            expected = {16'((received * 2 + 1) & 65535), 16'((received * 2) & 65535)};
            if (output_data !== expected || last !== (received == 86527))
                $fatal(1, "word %0d got %h expected %h last %b", received, output_data, expected, last);
            received <= received + 1;
        end
    end
    task byte_in(input [7:0] value);
        @(negedge pclk); data = value; href = 1;
    endtask
    initial begin
        #1000; resetn = 1;
        #1000; control[4] = 1;
        #2000;
        @(negedge pclk); vsync = 1;
        repeat (8) @(negedge pclk);
        vsync = 0;
        for (integer y = 0; y < 416; y = y + 1) begin
            for (integer x = 0; x < 416; x = x + 1) begin
                byte_in(((y * 416 + x) >> 8) & 255);
                byte_in((y * 416 + x) & 255);
            end
            @(negedge pclk); href = 0;
            repeat (20) @(negedge pclk);
        end
        #20000;
        if (received != 86528 || !status[2] || status[1]) $fatal(1, "Frame validation failed");
        control[4] = 0; #2000; control[4] = 1; #2000;
        @(negedge pclk); vsync = 1;
        repeat (8) @(negedge pclk);
        vsync = 0;
        byte_in(0); byte_in(0);
        @(negedge pclk); href = 0;
        #2000;
        if (!status[1]) $fatal(1, "Short line was accepted");
        $display("PASS: 86528 packed words, TLAST, backpressure, rearm, short-line rejection");
        $finish;
    end
    initial begin #30000000; $fatal(1, "Simulation timeout"); end
endmodule
