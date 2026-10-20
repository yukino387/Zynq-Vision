module hdmi_scanout (
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 axi_clk CLK", X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF s_axis, ASSOCIATED_RESET resetn, FREQ_HZ 125000000" *) input wire axi_clk,
    (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 resetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire resetn,
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 pixel_clk CLK", X_INTERFACE_PARAMETER="FREQ_HZ 74250000" *) input wire pixel_clk,
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 serial_clk CLK", X_INTERFACE_PARAMETER="FREQ_HZ 371250000" *) input wire serial_clk,input wire locked,
    (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TDATA" *) input wire [31:0] s_axis_tdata,
    (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TVALID" *) input wire s_axis_tvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TREADY" *) output wire s_axis_tready,
    (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TLAST" *) input wire s_axis_tlast,
    (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TUSER" *) input wire s_axis_tuser,
    output wire [2:0] hdmi_data_p,output wire [2:0] hdmi_data_n,
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 hdmi_clk_p CLK", X_INTERFACE_PARAMETER="FREQ_HZ 74250000" *) output wire hdmi_clk_p,
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 hdmi_clk_n CLK", X_INTERFACE_PARAMETER="FREQ_HZ 74250000" *) output wire hdmi_clk_n,
    output wire [31:0] underflows
);
    (* ASYNC_REG="TRUE" *) reg [2:0] reset_pipe=0;
    always @(posedge pixel_clk or negedge locked)if(!locked)reset_pipe<=0;else reset_pipe<={reset_pipe[1:0],resetn};
    wire pixel_reset=!reset_pipe[2],fifo_reset=!resetn || !locked;
    wire full,empty,write_busy,read_busy;
    wire [17:0] head;
    wire active,hsync,vsync,frame_start,line_end;
    wire [10:0] x;wire [9:0] y;
    video_timing timing(pixel_clk,pixel_reset,active,hsync,vsync,frame_start,line_end,x,y);
    reg synchronized=0;
    reg [31:0] failures=0;
    wire available=!empty && !read_busy;
    wire aligned=available && ((frame_start && head[17]) || (!frame_start && synchronized && !head[17])) && head[16]==line_end;
    wire consume=active && aligned;
    wire discard=!active && !synchronized && available && !head[17];
    wire [23:0] rgb=consume?{head[15:11],head[15:13],head[10:5],head[10:9],head[4:0],head[4:2]}:24'b0;
    always @(posedge pixel_clk) begin
        if(pixel_reset) begin synchronized<=0;failures<=0;end
        else if(active)begin
            if(frame_start)synchronized<=aligned;
            else if(!aligned)synchronized<=0;
            if((frame_start || synchronized) && !aligned)failures<=failures+1'b1;
        end
    end
    assign s_axis_tready=!full && !write_busy && !fifo_reset;
    // Each 32-bit VDMA beat holds two RGB565 pixels, low pixel first.
    // SOF belongs to the first pixel and EOL to the second (1280 pixels/line).
    xpm_fifo_async #(.FIFO_MEMORY_TYPE("block"),.FIFO_WRITE_DEPTH(2048),.WRITE_DATA_WIDTH(36),.READ_DATA_WIDTH(18),.READ_MODE("fwft"),.FIFO_READ_LATENCY(0),.CDC_SYNC_STAGES(2),.USE_ADV_FEATURES("0000")) fifo (
        .rst(fifo_reset),.wr_clk(axi_clk),.wr_en(s_axis_tvalid && s_axis_tready),.din({1'b0,s_axis_tlast,s_axis_tdata[31:16],s_axis_tuser,1'b0,s_axis_tdata[15:0]}),.full(full),.wr_rst_busy(write_busy),
        .rd_clk(pixel_clk),.rd_en(consume || discard),.dout(head),.empty(empty),.rd_rst_busy(read_busy),.sleep(1'b0),.injectsbiterr(1'b0),.injectdbiterr(1'b0)
    );
    wire [9:0] red,green,blue;
    tmds_encoder encode_blue(pixel_clk,pixel_reset,active,hsync,vsync,rgb[7:0],blue);
    tmds_encoder encode_green(pixel_clk,pixel_reset,active,1'b0,1'b0,rgb[15:8],green);
    tmds_encoder encode_red(pixel_clk,pixel_reset,active,1'b0,1'b0,rgb[23:16],red);
    tmds_serializer serial_blue(pixel_clk,serial_clk,pixel_reset,blue,hdmi_data_p[0],hdmi_data_n[0]);
    tmds_serializer serial_green(pixel_clk,serial_clk,pixel_reset,green,hdmi_data_p[1],hdmi_data_n[1]);
    tmds_serializer serial_red(pixel_clk,serial_clk,pixel_reset,red,hdmi_data_p[2],hdmi_data_n[2]);
    tmds_serializer serial_clock(pixel_clk,serial_clk,pixel_reset,10'b1111100000,hdmi_clk_p,hdmi_clk_n);
    reg [31:0] gray_failures=0;
    always @(posedge pixel_clk) if(pixel_reset)gray_failures<=0;else gray_failures<=failures^(failures>>1);
    (* ASYNC_REG="TRUE" *) reg [31:0] sync1=0,sync2=0;
    always @(posedge axi_clk)begin sync1<=gray_failures;sync2<=sync1;end
    assign underflows=sync2;
endmodule
